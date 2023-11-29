from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from pdpyras import APISession

if TYPE_CHECKING:
    from collections.abc import Generator
    from datetime import datetime

    from requests import Response

logger = logging.getLogger(__name__)


class PagerdutyClient:
    api_key = settings.PAGERDUTY_API_KEY
    session = APISession(api_key, default_from=settings.PAGERDUTY_ACCOUNT_EMAIL)
    session.raise_if_http_error = True

    def get_schedule_on_call_users(
        self, schedule: str, since: datetime, until: datetime
    ) -> Response:
        if since is not None and until is not None and since > until:
            raise ValueError("Since must be before until")

        return self.session.get(
            f"schedules/{schedule}/users",
            params={"since": str(since), "until": str(until)},
        )

    def get_user_contact_method(self, user_id: str, contact_method_id: str) -> Response:
        return self.session.get(f"users/{user_id}/contact_methods/{contact_method_id}")

    def get_all_services(self) -> Generator[Any, Any, Generator[Any, Any, None] | None]:
        return self.session.iter_all("services")

    def get_all_users(self) -> Generator[Any, Any, Generator[Any, Any, None] | None]:
        return self.session.iter_all("users", params={"include[]": "contact_methods"})

    def create_incident(
        self,
        title: str,
        pagerduty_id: str,
        details: str,
        incident_key: str,
        conference_url: str,
    ) -> Response:
        return self.session.post(
            url="incidents",
            json={
                "incident": {
                    "type": "incident",
                    "title": title,
                    "service": {"id": pagerduty_id, "type": "service_reference"},
                    "urgency": "high",
                    "incident_key": incident_key,
                    "body": {
                        "type": "incident_body",
                        "details": details,
                    },
                    "conference_bridge": {"conference_url": conference_url},
                }
            },
        )
