from __future__ import annotations

import logging
from typing import Any

from firefighter.pagerduty.client import PagerdutyClient

logger = logging.getLogger(__name__)


class PagerdutyService:
    """XXX Rename to PagerDutyClient to avoid confusion with PagerDutyService Django model."""

    logger: logging.Logger = logging.getLogger(__name__)
    client: PagerdutyClient

    def __init__(self) -> None:
        self.client = PagerdutyClient()

    def get_phone_number_from_body(self, pd_user: dict[str, Any]) -> str | None:
        phone_number = None
        contact_methods: list[dict[str, str | int | None]] = pd_user.get(
            "contact_methods", []
        )
        # Prefer "Work" phone number, get anything we can
        for summary in ["Work", "Mobile", "SMS", "Phone", "Home"]:
            # Get the first dict element of the list of contact methods with the right summary
            best_phone = next(
                (
                    contact_method
                    for contact_method in contact_methods
                    if contact_method["summary"] == summary
                    and (
                        contact_method["type"]
                        in {
                            "phone_contact_method",
                            "phone_contact_method_reference",
                            "sms_contact_method",
                        }
                    )
                ),
                None,
            )
            if best_phone:
                if best_phone["type"] in {"phone_contact_method", "sms_contact_method"}:
                    return f"{best_phone['country_code']}{best_phone['address']}"

                if (
                    best_phone["type"] == "phone_contact_method_reference"
                    and best_phone["id"] is not None
                ):
                    phone_number = self.get_user_phone_number(
                        pd_user["id"], str(best_phone["id"])
                    )
                    if phone_number is not None and phone_number != "":
                        return phone_number

        return phone_number

    def get_user_phone_number(
        self, pagerduty_user_id: str, contact_method_id: str
    ) -> str:
        contact_method: dict[str, Any] = (
            self.client.get_user_contact_method(pagerduty_user_id, contact_method_id)
        ).json()["contact_method"]
        if contact_method["type"] != "phone_contact_method":
            err_msg = f"Wrong contact method, expecting phone_contact_method, got {contact_method['type']}"
            raise AttributeError(err_msg)
        return f"{contact_method['country_code']}{contact_method['address']}"

    def get_all_oncalls(self) -> list[dict[str, Any]]:
        return self.client.session.list_all(
            "oncalls",
            params={"include[]": ["users", "schedules", "escalation_policies"]},
        )


pagerduty_service = PagerdutyService()
