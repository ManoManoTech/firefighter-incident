from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any, Final, cast

from django.conf import settings
from httpx import HTTPError
from jira.exceptions import JIRAError

from firefighter.firefighter.http_client import HttpClient
from firefighter.firefighter.utils import get_in
from firefighter.jira_app.client import JiraClient

if TYPE_CHECKING:
    from jira import Project

    from firefighter.jira_app.types import WorkflowBuilderResponse
    from firefighter.raid.types import (
        JiraObject,
    )

logger = logging.getLogger(__name__)

RAID_JIRA_PROJECT_KEY: Final[str] = settings.RAID_JIRA_PROJECT_KEY
# XXX Do not hardcode this, it should be a setting or fetched from Jira
RAID_JIRA_WORKFLOW_NAME: Final[str] = "Incident workflow - v2023.03.13"
TARGET_STATUS_NAME: Final[str] = "Closed"


class JiraAttachmentError(Exception):
    pass


class RaidJiraClient(JiraClient):
    def create_issue(  # noqa: PLR0912, PLR0913, C901, PLR0917
        self,
        issuetype: str | None,
        summary: str,
        description: str,
        assignee: str | None,
        reporter: str,
        priority: int | None,
        labels: list[str] | None = None,
        zoho_desk_ticket_id: str | int | None = None,
        zendesk_ticket_id: str | int | None = None,
        is_seller_in_golden_list: bool | None = None,  # noqa: FBT001
        is_key_account: bool | None = None,  # noqa: FBT001
        seller_contract_id: int | str | None = None,
        suggested_team_routing: str | None = None,
        business_impact: str | None = None,
        platform: str | None = None,
        area: str | None = None,
        environments: list[str] | None = None,
        project: str | None = None,
        qualifier: str | None = None,
    ) -> JiraObject:
        description_addendum: list[str] = []
        extra_args: dict[str, Any] = {}
        if assignee:
            extra_args["assignee"] = {"id": assignee}
        if qualifier:
            extra_args["customfield_10892"] = {"id": qualifier}
        if labels is None:
            labels = [""]
        if priority is None:
            priority_value = "-"
        else:
            if not 1 <= priority <= 4:
                raise ValueError("Priority must be between 1 and 4")
            priority_value = str(priority)
        if area:
            extra_args["customfield_10920"] = str(area)
        if zoho_desk_ticket_id:
            extra_args["customfield_10896"] = str(zoho_desk_ticket_id)
        if zendesk_ticket_id:
            extra_args["customfield_10895"] = str(zendesk_ticket_id)
        if seller_contract_id:
            description_addendum.append(
                f"Seller link to BO: https://bo.monechelle.com/provider/catalog/listproducts?provider_id={seller_contract_id}"
            )
            extra_args["customfield_10908"] = str(seller_contract_id)
        if is_seller_in_golden_list:
            labels = [*labels, "goldenList"]
        if is_key_account:
            labels = [*labels, "keyAccount"]
        if suggested_team_routing and suggested_team_routing != "SBI":
            description_addendum.append(
                f"Suggested team to be routed: *{suggested_team_routing}*"
            )
        if business_impact and business_impact != "N/A":
            if business_impact not in {"Low", "Medium", "High"}:
                raise ValueError("Business impact must be Low, Medium or High")
            extra_args["customfield_10936"] = {"value": business_impact}
        if platform:
            platform = platform.replace("platform-", "")
            extra_args["customfield_10201"] = {"value": platform}
        if environments:
            extra_args["customfield_11049"] = [{"value": e} for e in environments]

        if len(description_addendum) > 0:
            description_addendum_str = "\n *Additional Information* \n" + "\n".join(
                description_addendum
            )
            description += description_addendum_str
        project = project if project else RAID_JIRA_PROJECT_KEY
        issue = self.jira.create_issue(
            project=project,
            summary=summary,
            description=description,
            issuetype={"name": issuetype},
            reporter={"id": reporter},
            customfield_11064={"value": priority_value},
            labels=labels,
            **extra_args,
        )
        return self._jira_object(issue.raw)

    def get_projects(self) -> list[Project]:
        return self.jira.projects()

    @staticmethod
    def add_attachments_to_issue(issue_id: str | int, urls: list[str]) -> None:
        """Add attachments to a Jira issue.

        Args:
            issue_id (str | int): the Jira issue id
            urls (list[str]): list of urls to the attachments

        Raises:
            JiraAttachmentError: if there is an error while adding any attachment
        """
        http_client = HttpClient()
        for i, url in enumerate(urls):
            index = url.rfind(".")
            extension = url[index:]
            try:
                response = http_client.get(url)
                response.raise_for_status()  # Raises an exception if status code is not 2XX

                in_memory_file = io.BytesIO(response.content)

                client.jira.add_attachment(
                    issue=issue_id,
                    attachment=in_memory_file,
                    filename=f"image{i}{extension}",
                )

            except (HTTPError, JIRAError) as err:
                msg = f"Error while adding attachment to issue: {err}"
                raise JiraAttachmentError(msg) from err

    def close_issue(
        self,
        issue_id: str | int,
    ) -> None:
        return self.transition_issue_auto(
            issue_id, TARGET_STATUS_NAME, RAID_JIRA_WORKFLOW_NAME
        )

    def _get_project_config_workflow(
        self, project_key: str = RAID_JIRA_PROJECT_KEY
    ) -> dict[str, Any]:
        return self._get_project_config_workflow_base(
            project_key, RAID_JIRA_WORKFLOW_NAME
        )

    def _get_project_config_workflow_from_builder(self) -> WorkflowBuilderResponse:
        return self._get_project_config_workflow_from_builder_base(
            RAID_JIRA_WORKFLOW_NAME
        )

    @staticmethod
    def _jira_object(issue: dict[str, Any]) -> JiraObject:
        if issue_id := issue.get("id"):
            jira_id = int(cast(str, issue_id))
        else:
            raise TypeError("Jira ID not found")

        jira_key = issue.get("key")
        jira_assignee_id = get_in(issue, ["fields", "assignee", "accountId"])
        jira_reporter_id = get_in(issue, ["fields", "reporter", "accountId"])
        jira_description = get_in(issue, ["fields", "description"])
        jira_summary = get_in(issue, ["fields", "summary"])
        jira_issue_type = get_in(issue, ["fields", "issuetype", "name"])
        # If any field is not string
        if None in {
            jira_reporter_id,
            jira_description,
            jira_summary,
            jira_issue_type,
        }:
            raise TypeError("Jira object has wrong type")

        if jira_key is None:
            raise TypeError("Jira key is None")

        return {
            "id": jira_id,
            "key": jira_key,
            "project_key": str(jira_key.split("-")[0]),
            "assignee_id": jira_assignee_id,
            "reporter_id": jira_reporter_id,
            "description": jira_description,
            "summary": jira_summary,
            "issue_type": jira_issue_type,
            "business_impact": get_in(
                issue, ["fields", "customfield_10936", "value"], default=""
            ),
        }


client = RaidJiraClient()
