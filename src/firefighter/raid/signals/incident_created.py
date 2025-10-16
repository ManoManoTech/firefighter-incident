from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.dispatch.dispatcher import receiver

from firefighter.jira_app.client import JiraAPIError, JiraUserNotFoundError
from firefighter.raid.client import client
from firefighter.raid.forms import prepare_jira_fields
from firefighter.raid.models import JiraTicket
from firefighter.raid.service import get_jira_user_from_user
from firefighter.slack.messages.slack_messages import (
    SlackMessageIncidentDeclaredAnnouncement,
)
from firefighter.slack.signals import incident_channel_done

if TYPE_CHECKING:
    from firefighter.incidents.models.incident import Incident
    from firefighter.slack.models.incident_channel import IncidentChannel

logger = logging.getLogger(__name__)
RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID
APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME


@receiver(signal=incident_channel_done)
def create_ticket(
    sender: Any, incident: Incident, channel: IncidentChannel, **kwargs: Any
) -> JiraTicket:
    # pylint: disable=unused-argument

    # Extract jira_extra_fields and impacts_data from kwargs (passed from unified incident form)
    jira_extra_fields = kwargs.get("jira_extra_fields", {})
    impacts_data = kwargs.get("impacts_data", {})
    logger.info(f"CREATE_TICKET - kwargs keys: {list(kwargs.keys())}")
    logger.info(f"CREATE_TICKET - jira_extra_fields received: {jira_extra_fields}")

    jira_user = get_jira_user_from_user(incident.created_by)
    account_id = jira_user.id

    # Map Impact priority (1-5) to JIRA priority (1-5), fallback to P1 for invalid values
    priority: int = incident.priority.value if 1 <= incident.priority.value <= 5 else 1

    # Build enhanced description with incident metadata
    description = f"""{incident.description}\n
\n
🧯 This incident has been created for a critical incident. Links below to Slack and {APP_DISPLAY_NAME}.\n
📦 Incident category: {incident.incident_category.name} ({incident.incident_category.group.name})\n
{incident.priority.emoji} Priority: {incident.priority.name}\n"""

    # Prepare all Jira fields using the common function
    # P1-P3 use first environment only (for backward compatibility)
    environments = jira_extra_fields.get("environments", [incident.environment.value])
    platforms = jira_extra_fields.get("platforms", ["platform-All"])

    jira_fields = prepare_jira_fields(
        title=incident.title,
        description=description,
        priority=priority,
        reporter=account_id,
        incident_category=incident.incident_category.name,
        environments=[environments[0]] if environments else [incident.environment.value],  # P1-P3: first only
        platforms=platforms,
        impacts_data=impacts_data,
        optional_fields={
            "zendesk_ticket_id": jira_extra_fields.get("zendesk_ticket_id", ""),
            "seller_contract_id": jira_extra_fields.get("seller_contract_id", ""),
            "zoho_desk_ticket_id": jira_extra_fields.get("zoho_desk_ticket_id", ""),
            "is_key_account": jira_extra_fields.get("is_key_account"),
            "is_seller_in_golden_list": jira_extra_fields.get("is_seller_in_golden_list"),
            "suggested_team_routing": jira_extra_fields.get("suggested_team_routing"),
        },
    )

    # Create Jira issue with all prepared fields
    issue = client.create_issue(**jira_fields)
    issue_id = issue.get("id")
    if issue_id is None:
        logger.error(f"Could not create Jira ticket for incident {incident.id}")
        raise JiraAPIError("Could not create Jira ticket")
    try:
        default_jira_user = client.get_jira_user_from_jira_id(
            RAID_DEFAULT_JIRA_QRAFT_USER_ID
        )
    except JiraUserNotFoundError:
        logger.exception(
            f"Could not find Jira default reporter user with account id {RAID_DEFAULT_JIRA_QRAFT_USER_ID}"
        )
    # Add watcher reporter
    try:
        client.jira.add_watcher(issue=issue_id, watcher=account_id)
    except JiraAPIError:
        logger.exception(
            f"Could not add the watcher with account id {account_id} to the ticket {issue_id}"
        )
        # Removing default watcher TeamQraft
        try:
            client.jira.remove_watcher(issue=issue_id, watcher=default_jira_user)
        except JiraAPIError:
            logger.exception(
                f"Could not remove the watcher {default_jira_user} to the ticket {issue_id}"
            )

    client.jira.add_simple_link(
        issue=str(issue_id),
        object={
            "url": incident.status_page_url,
            "title": f"{APP_DISPLAY_NAME} incident #{incident.id}",
        },
    )

    client.jira.add_simple_link(
        issue=str(issue_id),
        object={"url": channel.link, "title": f"Slack conversation #{channel.name}"},
    )
    issue["business_impact"] = issue.get("business_impact", "")
    jira_ticket = JiraTicket.objects.create(**issue, incident=incident)

    channel.add_bookmark(
        title="Jira ticket",
        link=jira_ticket.url,
        emoji=":jira_new:",
    )

    channel.send_message_and_save(SlackMessageIncidentDeclaredAnnouncement(incident))

    return jira_ticket
