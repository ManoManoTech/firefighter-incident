from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Never

from django.conf import settings
from django.dispatch.dispatcher import receiver

from firefighter.jira_app.client import JiraAPIError, JiraUserNotFoundError
from firefighter.raid.client import client
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
    sender: Any, incident: Incident, channel: IncidentChannel, **kwargs: Never
) -> JiraTicket:
    # pylint: disable=unused-argument

    jira_user = get_jira_user_from_user(incident.created_by)
    account_id = jira_user.id
    # XXX Better description
    # XXX Custom field with FireFighter ID/link?
    # XXX Set affected environment custom field
    # XXX Set custom field impacted area to group/domain?
    priority: int = incident.priority.value if 1 <= incident.priority.value <= 4 else 1
    issue = client.create_issue(
        issuetype="Incident",
        summary=incident.title,
        description=f"""{incident.description}\n
\n
🧯 This incident has been created for a critical incident. Links below to Slack and {APP_DISPLAY_NAME}.\n
📦 Component: {incident.component.name} ({incident.component.group.name})\n
{incident.priority.emoji} Priority: {incident.priority.name}\n""",
        assignee=None,
        reporter=account_id,
        priority=priority,
    )
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
