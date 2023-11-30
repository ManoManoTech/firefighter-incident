from __future__ import annotations

import logging
from functools import cache, cached_property
from typing import TYPE_CHECKING, Any, Literal, Never

from django.conf import settings
from jinja2 import Environment
from jinja2.environment import Template
from jinja2.loaders import PackageLoader

from firefighter.firefighter.utils import get_in

if TYPE_CHECKING:
    from firefighter.confluence.client import ConfluenceClient
    from firefighter.confluence.utils import ConfluencePage, ConfluencePageId, PageInfo
    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)
SLACK_CURRENT_ONCALL_URL: str = settings.SLACK_CURRENT_ONCALL_URL


@cache
def get_confluence_client() -> type[ConfluenceClient]:
    # ruff: noqa: PLC0415
    from firefighter.confluence.client import ConfluenceClient

    return ConfluenceClient


class ConfluenceService:
    """Provide methods to interact with Confluence, without regards to the underlying library or HTTP client used.

    TODO: The service should provide Pythonic errors and return types, and should not leak the underlying library or Confluence errors.
    It is not a priority for now, as the Confluence API is not used in critical paths.
    """

    logger = logging.getLogger(__name__)
    jinja: Environment
    _client: ConfluenceClient | None

    POSTMORTEM_FOLDER_ID: ConfluencePageId = int(
        settings.CONFLUENCE_POSTMORTEM_FOLDER_ID
    )
    POSTMORTEM_TEMPLATE_PAGE_ID: ConfluencePageId = int(
        settings.CONFLUENCE_POSTMORTEM_TEMPLATE_PAGE_ID
    )
    RUNBOOKS_FOLDER_ID: ConfluencePageId = int(settings.CONFLUENCE_RUNBOOKS_FOLDER_ID)
    DEFAULT_SPACE: str = settings.CONFLUENCE_POSTMORTEM_SPACE

    base_url: str = settings.CONFLUENCE_URL.removesuffix("/rest/api")
    """Confluence base URL. (with `/wiki`, without `/rest/api`)"""

    def __init__(self) -> None:
        self._client = None
        self.jinja = self._build_template_engine()

    @cached_property
    def client(self) -> ConfluenceClient:
        if self._client is None:
            self._client = get_confluence_client()(
                settings.CONFLUENCE_URL,
                settings.CONFLUENCE_USERNAME,
                settings.CONFLUENCE_API_KEY,
            )
        return self._client

    @staticmethod
    def _build_template_engine() -> Environment:
        return Environment(
            loader=PackageLoader("firefighter.confluence", "templates"), autoescape=True
        )

    def _build_page_from_template(
        self, template: Template | str, *_: Never, **kwargs: Any
    ) -> str:
        """Returns a unicode string, from a Jinja template (or path) and its arguments, if any."""
        template = self.jinja.get_template(template)
        rendered_page = template.render(kwargs)
        logger.debug(rendered_page)
        return rendered_page

    def parse_confluence_page(self, pm: dict[str, Any] | ConfluencePage) -> PageInfo:
        """Helper to parse a Confluence page into a PageInfo object.

        Args:
            pm (dict[str, Any] | ConfluencePage): ConfluencePage from the API, or a dict with the same structure.

        Returns:
            PageInfo: The parsed page details that are present on [confluence.models.ConfluencePage][].

        Raises:
            TypeError: If one of page_id, page_title, page_url or page_edit_url are not strings.
        """
        page_url = f'{self.base_url}{get_in(pm, "_links.webui")}'
        page_edit_url = f'{self.base_url}{get_in(pm, "_links.editui")}'

        page_id = str(pm.get("id"))
        page_title = pm.get("title")
        if not isinstance(page_id, str):
            raise TypeError("page_id is not a string")
        if not isinstance(page_title, str):
            raise TypeError("page_title is not a string")
        if not isinstance(page_url, str):
            raise TypeError("page_url is not a string")
        if not isinstance(page_edit_url, str):
            raise TypeError("page_edit_url is not a string")
        return {
            "name": page_title,
            "page_id": page_id,
            "page_url": page_url,
            "page_edit_url": page_edit_url,
        }

    def update_oncall_page(self, users: dict[str, User]) -> bool:
        """Update the Confluence list of On-Call users, if the page needs to be updated.
        Users should have a SlackUser AND a PagerDutyUser associated.

        Args:
            users (list[User]): list of Users to update the page with.

        Returns:
            bool: has the page been updated?
        """
        content = (self.client.get_page(settings.CONFLUENCE_ON_CALL_PAGE_ID)).json()

        page_version = get_in(content, "version.number")
        if not page_version:
            logger.error("No page version in Confluence page! %s", content)
            return False
        page_version += 1
        page_body = self._build_page_from_template(
            "oncall_team.xml.j2",
            users=users.items(),
            oncall_page_link=SLACK_CURRENT_ONCALL_URL,
        )

        logger.debug("Confluence OnCall page body: %s", page_body)
        if get_in(content, "body.storage.value") != page_body:
            res = self.client.update_page(
                content.get("id"),
                content.get("type"),
                content.get("title"),
                page_body,
                page_version,
            )
            if res.status_code != 200:
                logger.error("Can't update OnCall page: %s", res.json())
                return False
            return True

        logger.info("Confluence OnCall page is up to date, and was not updated.")
        return False

    def create_postmortem(
        self, title: str, incident: Incident
    ) -> None | ConfluencePage:
        """Create the PostMortem page of an incident.

        Args:
            title (str): Title of the PostMortem page.
            incident (Incident): Incident object.

        Returns:
            None | ConfluencePage: The newly created page, or None if it failed.
        """
        # Get the body from the template page
        postmortem_template = (
            self.client.get_page(self.POSTMORTEM_TEMPLATE_PAGE_ID)
        ).json()
        body = get_in(postmortem_template, "body.storage.value")
        logger.debug(body)

        # Load body as Jinja template
        # XXX make sure this is safe
        pm_template_jinja = Template(source=body)
        pm_body = self._build_page_from_template(
            pm_template_jinja, incident=incident.__dict__
        )
        # Create the postmortem with the template body
        page_created: ConfluencePage = self.create_page(
            title, self.POSTMORTEM_FOLDER_ID, pm_body
        )

        logger.debug("Postmortem page id: %s ", page_created.get("id"))
        if "statusCode" in page_created:
            logger.error(
                f"Can't create postmortem page with title {title}: {page_created}"
            )
            return None
        logger.debug(page_created)
        return page_created

    def get_page_children_pages(
        self, page_id: ConfluencePageId, *args: Any, **kwargs: Any
    ) -> list[ConfluencePage]:
        """Get all children pages of a given page.
        TODO: testing.

        Args:
            page_id (ConfluencePageId): ID of the page to get children pages from.
            *args: Arguments to pass to Confluence.
            **kwargs: Keyword arguments to pass to Confluence.

        Returns:
            list[ConfluencePage]: list of children pages.
        """
        return list(self.client.get_page_children_pages(page_id, *args, **kwargs))

    def get_page_descendant_pages(
        self, page_id: ConfluencePageId, *args: Any, **kwargs: Any
    ) -> list[ConfluencePage]:
        """Get all descendant (nested children) pages of a given page.
        TODO: Pagination support and testing.

        Args:
            page_id (ConfluencePageId): ID of the page to get children pages from.
            *args: Arguments to pass to Confluence.
            **kwargs: Keyword arguments to pass to Confluence.

        Returns:
            list[ConfluencePage]: list of children pages.
        """
        return self.client.get_page_descendant_pages(page_id, *args, **kwargs).json()[
            "results"
        ]

    def get_page(self, page_id: ConfluencePageId) -> ConfluencePage:
        """TODO: Errors.

        Args:
            page_id (ConfluencePageId): ID of the page to get.

        Returns:
            ConfluencePage: The page.
        """
        return self.client.get_page(page_id).json()

    def get_page_with_body_and_version(
        self, page_id: ConfluencePageId
    ) -> ConfluencePage:
        return self.client.get_page_body_and_version(page_id).json()

    def create_page(
        self,
        title: str,
        parent_id: ConfluencePageId,
        body: str,
        space: str | None = None,
    ) -> ConfluencePage:
        """TODO: Errors.

        Args:
            title (str): Title of the page to create.
            parent_id (ConfluencePageId): Where to create the page. Will be a child of this page.
            body (str): Body of the page.
            space (str | None, optional): Space to create the page in. If None, defaults to theService's default space. Defaults to None.

        Returns:
            ConfluencePage: The newly created page.
        """
        if not space:
            space = self.DEFAULT_SPACE
        return self.client.create_page(title, parent_id, space, body).json()

    def move_page(
        self,
        page_id: ConfluencePageId,
        target_page_id: ConfluencePageId,
        position: Literal["before", "after", "append"] = "append",
        *,
        dry_run: bool = False,
    ) -> None | ConfluencePage:
        """Args:
            page_id (ConfluencePageId): ID of the page to move.
            target_page_id (ConfluencePageId): ID of the parent page to move the page in relation to.
            position (Literal["before", "after", "append"], optional): Where should the page be moved, in relation to the target page. Defaults to "append".
            dry_run (bool, optional): If True, will log instead of moving. Defaults to False.

        Returns:
            None | ConfluencePage: The moved page, or None if it failed.
        """
        if dry_run:
            logger.info(
                f"Would have moved {page_id} {'into' if position == 'append' else position} {target_page_id} if not dry run"
            )
            return None

        res = self.client.move_page(page_id, target_page_id, position)
        logger.info(
            f"Moved {page_id} {'into' if position == 'append' else position} {target_page_id}"
        )
        if res.status_code == 200:
            return res.json()
        logger.error(f"Error moving page {page_id} {res.status_code} {res.text}")
        return None

    def sort_pages(
        self,
        page_ids: list[tuple[ConfluencePageId, ConfluencePage]],
        *,
        dry_run: bool = False,
    ) -> None:
        """Sort pages according to the list order.

        **Be careful**:
        - this will move pages around, and will not check if the pages are already in the right order.
        - this will not check that the pages are in the same parent.
        - this will perform n moves, where n is the number of pages in the list.

        Args:
            page_ids (list[tuple[ConfluencePageId, ConfluencePage]]): Sorted list of (PageId, Page) tuples.
            dry_run (bool, optional): If True, will log instead of sorting. Defaults to False.
        """
        for index, page in enumerate(page_ids):
            if index == 0:
                continue

            target_id = page_ids[index - 1][0]
            page_id = page[0]
            self.move_page(
                page_id,
                target_id,
                position="after",
                dry_run=dry_run,
            )


confluence_service = ConfluenceService()
if settings.CONFLUENCE_MOCK_CREATE_POSTMORTEM:
    from random import randint

    confluence_service.create_postmortem = lambda title, _incident: {  # type: ignore
        "id": str(randint(10, 99999)),  # nosec: B311 # noqa: S311
        "type": "page",
        "status": "current",
        "title": title,
        "space": {
            "id": 9999,
            "key": f"{settings.CONFLUENCE_POSTMORTEM_SPACE}",
            "name": "Pulse",
            "type": "global",
            "status": "current",
            "_expandable": {
                "settings": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}/settings",
                "metadata": "",
                "operations": "",
                "lookAndFeel": f"/rest/api/settings/lookandfeel?spaceKey={settings.CONFLUENCE_POSTMORTEM_SPACE}",
                "identifiers": "",
                "permissions": "",
                "icon": "",
                "description": "",
                "theme": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}/theme",
                "history": "",
                "homepage": "/rest/api/content/13243546",
            },
            "_links": {
                "webui": f"/spaces/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                "self": f"{settings.CONFLUENCE_URL}/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
            },
        },
        "history": {
            "latest": True,
            "createdBy": {
                "type": "known",
                "accountId": "abc1234",
                "accountType": "atlassian",
                "email": "john.doe@manomano.com",
                "publicName": "FireFighter",
                "profilePicture": {
                    "path": "/wiki/aa-avatar/abc1234",
                    "width": 48,
                    "height": 48,
                    "isDefault": False,
                },
                "displayName": "FireFighter",
                "isExternalCollaborator": False,
                "_expandable": {"operations": "", "personalSpace": ""},
                "_links": {"self": f"{settings.CONFLUENCE_URL}/user?accountId=abc1234"},
            },
            "createdDate": "2021-06-09T09:58:10.209Z",
            "_expandable": {
                "lastUpdated": "",
                "previousVersion": "",
                "contributors": "",
                "nextVersion": "",
            },
            "_links": {"self": f"{settings.CONFLUENCE_URL}/content/012345/history"},
        },
        "version": {
            "by": {
                "type": "known",
                "accountId": "abc1234",
                "accountType": "atlassian",
                "email": "john.doe@manomano.com",
                "publicName": "FireFighter",
                "profilePicture": {
                    "path": "/wiki/aa-avatar/abc1234",
                    "width": 48,
                    "height": 48,
                    "isDefault": False,
                },
                "displayName": "FireFighter",
                "isExternalCollaborator": False,
                "_expandable": {"operations": "", "personalSpace": ""},
                "_links": {"self": f"{settings.CONFLUENCE_URL}/user?accountId=abc1234"},
            },
            "when": "2021-06-09T09:58:10.209Z",
            "friendlyWhen": "il y a juste un instant",
            "message": "",
            "number": 1,
            "minorEdit": False,
            "confRev": "confluence$content$012345.2",
            "contentTypeModified": False,
            "_expandable": {
                "collaborators": "",
                "content": "/rest/api/content/012345",
            },
            "_links": {"self": f"{settings.CONFLUENCE_URL}/content/012345/version/1"},
        },
        "ancestors": [
            {
                "id": "13243546",
                "type": "page",
                "status": "current",
                "title": "Pulse",
                "macroRenderedOutput": {},
                "extensions": {"position": 321067586},
                "_expandable": {
                    "container": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                    "metadata": "",
                    "restrictions": "/rest/api/content/13243546/restriction/byOperation",
                    "history": "/rest/api/content/13243546/history",
                    "body": "",
                    "version": "",
                    "descendants": "/rest/api/content/13243546/descendant",
                    "space": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                    "childTypes": "",
                    "operations": "",
                    "schedulePublishDate": "",
                    "children": "/rest/api/content/13243546/child",
                    "ancestors": "",
                },
                "_links": {
                    "self": f"{settings.CONFLUENCE_URL}/content/13243546",
                    "tinyui": "/x/lwAPfg",
                    "editui": "/pages/resumedraft.action?draftId=13243546",
                    "webui": f"/spaces/{settings.CONFLUENCE_POSTMORTEM_SPACE}/overview",
                },
            },
            {
                "id": "9998765",
                "type": "page",
                "status": "current",
                "title": "Incident Management",
                "macroRenderedOutput": {},
                "extensions": {"position": 159620941},
                "_expandable": {
                    "container": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                    "metadata": "",
                    "restrictions": "/rest/api/content/9998765/restriction/byOperation",
                    "history": "/rest/api/content/9998765/history",
                    "body": "",
                    "version": "",
                    "descendants": "/rest/api/content/9998765/descendant",
                    "space": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                    "childTypes": "",
                    "operations": "",
                    "schedulePublishDate": "",
                    "children": "/rest/api/content/9998765/child",
                    "ancestors": "",
                },
                "_links": {
                    "self": f"{settings.CONFLUENCE_URL}/content/9998765",
                    "tinyui": "/x/goYSXQ",
                    "editui": "/pages/resumedraft.action?draftId=9998765",
                    "webui": f"/spaces/{settings.CONFLUENCE_POSTMORTEM_SPACE}/pages/9998765/Incident+Management",
                },
            },
            {
                "id": "00012",
                "type": "page",
                "status": "current",
                "title": "Postmortems",
                "macroRenderedOutput": {},
                "extensions": {"position": 976},
                "_expandable": {
                    "container": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                    "metadata": "",
                    "restrictions": "/rest/api/content/00012/restriction/byOperation",
                    "history": "/rest/api/content/00012/history",
                    "body": "",
                    "version": "",
                    "descendants": "/rest/api/content/00012/descendant",
                    "space": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                    "childTypes": "",
                    "operations": "",
                    "schedulePublishDate": "",
                    "children": "/rest/api/content/00012/child",
                    "ancestors": "",
                },
                "_links": {
                    "self": f"{settings.CONFLUENCE_URL}/content/00012",
                    "tinyui": "/x/_oC5Tw",
                    "editui": "/pages/resumedraft.action?draftId=00012",
                    "webui": f"/spaces/{settings.CONFLUENCE_POSTMORTEM_SPACE}/pages/00012/Postmortems",
                },
            },
        ],
        "container": {
            "id": 9999,
            "key": f"{settings.CONFLUENCE_POSTMORTEM_SPACE}",
            "name": "Pulse",
            "type": "global",
            "status": "current",
            "history": {
                "createdBy": {
                    "type": "known",
                    "accountId": "abc1234",
                    "accountType": "atlassian",
                    "email": "",
                    "publicName": "John DOE",
                    "profilePicture": {
                        "path": "/wiki/aa-avatar/abc1234",
                        "width": 48,
                        "height": 48,
                        "isDefault": False,
                    },
                    "displayName": "John DOE",
                    "isExternalCollaborator": False,
                    "_expandable": {"operations": "", "personalSpace": ""},
                    "_links": {
                        "self": f"{settings.CONFLUENCE_URL}/user?accountId=abc1234"
                    },
                },
                "createdDate": "2020-10-13T08:34:55.098Z",
            },
            "_expandable": {
                "settings": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}/settings",
                "metadata": "",
                "operations": "",
                "lookAndFeel": f"/rest/api/settings/lookandfeel?spaceKey={settings.CONFLUENCE_POSTMORTEM_SPACE}",
                "identifiers": "",
                "permissions": "",
                "icon": "",
                "description": "",
                "theme": f"/rest/api/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}/theme",
                "homepage": "/rest/api/content/13243546",
            },
            "_links": {
                "webui": f"/spaces/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
                "self": f"{settings.CONFLUENCE_URL}/space/{settings.CONFLUENCE_POSTMORTEM_SPACE}",
            },
        },
        "macroRenderedOutput": {},
        "body": {
            "storage": {
                "value": '<p><span style="color: rgb(255,86,48);">&rarr; Delete all the red messages after your did what they say, starting by this one </span><ac:emoticon ac:name="smile" ac:emoji-shortname=":slight_smile:" ac:emoji-id="1f642" ac:emoji-fallback="🙂" /> <br /><br /><strong>Post-mortem published date</strong> YYYY-MM-DD</p><h2><strong>Incident Summary</strong></h2><p><em><strong><span style="color: rgb(255,86,48);">&rarr; Short</span></strong><span style="color: rgb(255,86,48);"> sentence or two summarizing the contributing factors, timeline summary, and the impact.</span></em><br /><em><span style="color: rgb(255,86,48);">E.g. &quot;On the morning of August 19th, we suffered a 1 minute SEV-1 due to a runaway process on our primary database.</span></em><br /><em><span style="color: rgb(255,86,48);">This database slowness introduced some slowdowns for users and we were out off SLA on our Global Health SLO&rdquo;.</span></em></p><h2><strong>Timeline (</strong><a href="https://www.timeanddate.com/time/zones/cet"><strong>Timezone CEST - Central European Summer Time</strong></a><strong> - military time)</strong></h2><p>February 1st 2021<span style="color: rgb(151,160,175);"> </span><span style="color: rgb(255,86,48);">(&rarr; Add the date before bullets if useful, don&rsquo;t use AM/PM&nbsp;Notation but Military time 00:00 until 23:59).</span></p><ul><li><p>XX:XX - Incident starts</p></li></ul><h2><strong>Root cause(s)</strong></h2><p>&hellip;</p><h2><strong>Impact</strong></h2><p>&hellip;</p><h2><strong>Resolution</strong></h2><p>&hellip;</p><h2><strong>Remediation and preventive measure(s)</strong></h2><p><em><span style="color: rgb(255,86,48);">&rarr; Did you receive an alert related to what you know is happening? Did the alert behave as you&rsquo;d expect?</span></em><br /><em><span style="color: rgb(255,86,48);">What tools were helpful (or unhelpful) during the incident? What did you learn/observe during the incident?</span></em><br /><em><span style="color: rgb(255,86,48);">How could you improve this impacted services? Are the service architecture &amp; behaviors clear to everyone?</span></em><br /><em><span style="color: rgb(255,86,48);">Have the roles been well distributed and performed?</span></em></p><ac:task-list>\n<ac:task>\n<ac:task-id>6</ac:task-id>\n<ac:task-status>incomplete</ac:task-status>\n<ac:task-body><span class="placeholder-inline-tasks">Task 1</span></ac:task-body>\n</ac:task>\n</ac:task-list><h2><strong>Closing the incident</strong></h2><ac:task-list>\n<ac:task>\n<ac:task-id>3</ac:task-id>\n<ac:task-status>incomplete</ac:task-status>\n<ac:task-body><span class="placeholder-inline-tasks">Link this post-mortem in the postmortems section of the application/service <a href="https://manomano.atlassian.net/wiki/spaces/SRE/pages/1305739687/Runbooks">runbook</a> and replace ms.foobar by the correct runbook in Appendix section below.</span></ac:task-body>\n</ac:task>\n<ac:task>\n<ac:task-id>4</ac:task-id>\n<ac:task-status>incomplete</ac:task-status>\n<ac:task-body><span class="placeholder-inline-tasks">Move this post-mortem to the corresponding [Archive] folder <u>ordered from the oldest to the most&nbsp;recent</u></span></ac:task-body>\n</ac:task>\n<ac:task>\n<ac:task-id>5</ac:task-id>\n<ac:task-status>incomplete</ac:task-status>\n<ac:task-body><span class="placeholder-inline-tasks"><a href="https://manomano.atlassian.net/wiki/spaces/SRE/pages/1327890703/Incident+Management+Automation#IncidentManagementAutomation-Closeanincident">Close the incident</a> using the incident bot</span></ac:task-body>\n</ac:task>\n</ac:task-list><h2><strong>Appendix</strong></h2><p>Runbook(s): <br />PostMortem(s):</p>',
                "representation": "storage",
                "embeddedContent": [],
                "_expandable": {"content": "/rest/api/content/012345"},
            },
            "_expandable": {
                "editor": "",
                "atlas_doc_format": "",
                "view": "",
                "export_view": "",
                "styled_view": "",
                "dynamic": "",
                "editor2": "",
                "anonymous_export_view": "",
            },
        },
        "extensions": {"position": 415300414},
        "_expandable": {
            "childTypes": "",
            "metadata": "",
            "operations": "",
            "schedulePublishDate": "",
            "children": "/rest/api/content/012345/child",
            "restrictions": "/rest/api/content/012345/restriction/byOperation",
            "descendants": "/rest/api/content/012345/descendant",
        },
        "_links": {
            "editui": "/pages/resumedraft.action?draftId=012345",
            "webui": f"/spaces/{settings.CONFLUENCE_POSTMORTEM_SPACE}/pages/012345",
            "context": "/wiki",
            "self": f"{settings.CONFLUENCE_URL}/content/012345",
            "tinyui": "/x/EIFMsQ",
            "collection": "/rest/api/content",
            "base": confluence_service.base_url,
        },
    }
