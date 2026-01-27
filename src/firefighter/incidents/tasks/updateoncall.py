from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from celery import shared_task
from django.conf import settings

from firefighter.slack.slack_templating import user_slack_handle_or_name

if TYPE_CHECKING:
    from celery import Signature

    from firefighter.incidents.models.user import User

if settings.ENABLE_PAGERDUTY:
    from firefighter.pagerduty.models import PagerDutyOncall
    from firefighter.pagerduty.tasks import fetch_oncalls
if settings.ENABLE_CONFLUENCE:
    from firefighter.confluence.service import confluence_service
if settings.ENABLE_SLACK:
    from firefighter.slack.models.conversation import Conversation
    from firefighter.slack.models.user import SlackUser

logger = logging.getLogger(__name__)

BASE_URL: str = settings.BASE_URL


@shared_task(name="incidents.update_oncall")
def update_oncall() -> None:
    """Fetch current on-calls and update the on-call Slack topic and Confluence page."""
    chain: Signature[bool] = (
        fetch_oncalls.s()  # pyright: ignore[reportUnboundVariable]
        | update_oncall_views.s()
    )
    chain()


@shared_task(name="incidents.update_oncall_views")
def update_oncall_views(*_args: Any, **_kwargs: Any) -> bool:
    """Updates the on-call Slack topic and Confluence page containing the info for the on-call personnel."""
    if not settings.ENABLE_PAGERDUTY:
        logger.error("Can't update on-call users without PagerDuty enabled.")
        return False

    oncall_users_grouped_per_ep = PagerDutyOncall.objects.get_current_oncalls_per_escalation_policy_name_first_responder()

    # Check that we have Slack ID and handle for these users, if needed
    if settings.ENABLE_SLACK:
        for user in oncall_users_grouped_per_ep.values():
            if not hasattr(user, "slack_user"):
                SlackUser.objects.add_slack_id_to_user(user)
                logger.debug("Added Slack ID to user: %s", user)
        update_oncall_slack_topic(oncall_users_grouped_per_ep)
    else:
        logger.warning("Not updating on-call Slack topic, Slack integration disabled.")

    update_oncall_confluence(oncall_users_grouped_per_ep)
    logger.info("Updated on-call users on Confluence and Slack topic.")
    return True


def create_oncall_topic(users: dict[str, User]) -> str:
    base_topic = f":uk: <{BASE_URL}|IT PRD SEV[1-3] incidents> - On-call: "
    for service_name, user in users.items():
        user_text = f"{service_name.upper()} "
        user_text += user_slack_handle_or_name(user) + " "
        if (
            hasattr(user, "pagerduty_user")
            and user.pagerduty_user
            and user.pagerduty_user.phone_number != ""
        ):
            user_text += f"<tel:+{user.pagerduty_user.phone_number}> "
        base_topic += user_text
    if len(base_topic) > 250:
        logger.warning(
            f'Tech channel on-call Slack topic is too long and will be cut at 250 chars: "{base_topic}"'
        )
    logger.debug(f"New on-call topic: {base_topic}.")
    return base_topic[:250]


def update_oncall_slack_topic(
    users: dict[str, User],
) -> bool:
    """TODO(gab) Move in the Slack app."""
    if not settings.ENABLE_SLACK:
        return False

    oncall_topic = create_oncall_topic(users)
    tech_incidents_conversation = Conversation.objects.get_or_none(tag="tech_incidents")
    if tech_incidents_conversation:
        res = tech_incidents_conversation.update_topic(oncall_topic)
        if res.get("ok"):
            logger.info(
                f"Updated on-call Slack topic on {tech_incidents_conversation}."
            )
            return True
    else:
        logger.warning(
            "Could not find tech_incidents conversation! Is there a channel with tag tech_incidents?"
        )
        return False
    logger.error("Failed to update on-call Slack topic.")
    return False


def update_oncall_confluence(users: dict[str, User]) -> bool:
    if not settings.ENABLE_CONFLUENCE:
        return False

    return confluence_service.update_oncall_page(users)
