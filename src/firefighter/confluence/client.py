from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firefighter.firefighter.http_client import HttpClient
from firefighter.firefighter.utils import get_in

if TYPE_CHECKING:
    from collections.abc import Generator

    import httpx

    from firefighter.confluence.utils import ConfluencePage, ConfluencePageId


class ConfluenceClient(HttpClient):
    """Helper methods for Confluence API.

    Should not be used directly, be used by [firefighter.confluence.service.ConfluenceService][].
    """

    base_url_api: str

    def __init__(self, base_url: str, username: str, api_key: str):
        super().__init__(client_kwargs={"auth": (username, api_key)})
        self.base_url_api = base_url
        """Confluence API base URL. (with `/wiki/rest/api`)"""
        self.base_url = self.base_url_api.removesuffix("/rest/api")
        """Confluence base URL. (with `/wiki`, without `/rest/api`)"""

    def _get_paged(
        self,
        url: str,
    ) -> Generator[ConfluencePage, None, None]:
        """From https://github.com/atlassian-api/atlassian-python-api/blob/master/atlassian/confluence.py
        Apache License 2.0.

        Args:
            url (str): The url to retrieve

        Yields:
            ConfluencePage: A generator object for the data elements
        """
        while True:
            response = self.get(
                url,
            ).json()
            if "results" not in response:
                return

            yield from response.get("results", [])

            # According to Cloud and Server documentation the links are returned the same way:
            # https://developer.atlassian.com/cloud/confluence/rest/api-group-content/#api-wiki-rest-api-content-get
            # https://developer.atlassian.com/server/confluence/pagination-in-the-rest-api/
            url_new = response.get("_links", {}).get("next")
            if url_new is None:
                break
            url = f"{self.base_url}{url_new}"

        return

    def get_page(
        self, page_id: str | int, expand: str = "body.storage,version"
    ) -> httpx.Response:
        return self.get(f"{self.base_url_api}/content/{page_id}?expand={expand}")

    def get_page_children_pages(
        self,
        page_id: str | int,
        expand: str = "version",
        limit: int = 200,
    ) -> Generator[ConfluencePage, None, None]:
        url = f"{self.base_url_api}/content/{page_id}/child/page?expand={expand}&limit={limit}"
        return self._get_paged(url)

    def get_page_body_and_version(
        self,
        page_id: str | int,
        expand: str = "body.storage,body.view,body.export_view,version",
    ) -> httpx.Response:
        return self.get(f"{self.base_url_api}/content/{page_id}?expand={expand}")

    def get_page_body_convert(
        self,
        value: Any,
        page_id: str | int,
        representation: str = "storage",
        expand: str = "webresource.tags.all,webresource.uris.all",
    ) -> httpx.Response:
        return self.post(
            f"{self.base_url_api}/contentbody/convert/styled_view?expand={expand}&contentIdContext={page_id}",
            json={"value": value, "representation": representation},
        )

    def move_page(
        self,
        page_id: int | str,
        target_page_id: int | str,
        mode: str = "append",
    ) -> httpx.Response:
        return self.put(
            f"{self.base_url_api}/content/{page_id}/move/{mode}/{target_page_id}",
        )

    def get_page_descendant_pages(
        self, page_id: ConfluencePageId, expand: str = "", limit: int = 500
    ) -> httpx.Response:
        return self.get(
            f"{self.base_url_api}/content/{page_id}/descendant/page?expand={expand}&limit={limit}"
        )

    def get_page_history(
        self,
        page_id: str | int,
        expand: str = "lastUpdated,previousVersion,contributors,body.storage",
    ) -> httpx.Response:
        return self.get(
            f"{self.base_url_api}/content/{page_id}/history?expand={expand}"
        )

    def get_page_versions(
        self, page_id: str | int, expand: str = "content.body.storage"
    ) -> httpx.Response:
        return self.get(
            f"{self.base_url_api}/content/{page_id}/version?expand={expand}"
        )

    def create_page(
        self,
        page_title: str,
        page_ancestor: str | int,
        page_space: str,
        page_body: str,
    ) -> httpx.Response:
        return self.post(
            f"{self.base_url_api}/content/",
            json={
                "type": "page",
                "title": page_title,
                "ancestors": [{"id": page_ancestor}],
                "space": {"key": page_space},
                "body": {"storage": {"value": page_body, "representation": "storage"}},
            },
        )

    def update_page(
        self,
        page_id: int,
        page_type: str,
        page_title: str,
        page_body: str,
        version_number: int,
    ) -> httpx.Response:
        return self.put(
            f"{self.base_url_api}/content/{page_id}",
            json={
                "id": page_id,
                "type": page_type,
                "title": page_title,
                "body": {"storage": {"value": page_body, "representation": "storage"}},
                "version": {"number": version_number},
            },
        )

    def update_title(
        self,
        page_id: int,
        page_title: str,
        page_type: str | None = "page",
        version_number: int | None = None,
    ) -> httpx.Response:
        if version_number is None or page_type is None:
            curr_page = self.get_page(page_id=page_id, expand="version")
            if version_number is None:
                version_number = int(get_in(curr_page.json(), "version.number")) + 1
            if page_type is None:
                page_type = get_in(curr_page.json(), "type")

        return self.put(
            f"{self.base_url_api}/content/{page_id}",
            json={
                "id": page_id,
                "type": page_type,
                "title": page_title,
                "version": {
                    "number": version_number,
                    "minorEdit": True,
                    "message": "Updated title automatically by FireFighter",
                },
            },
        )
