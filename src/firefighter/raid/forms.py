from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Never

from django import forms
from django.conf import settings
from django.db import models
from slack_sdk.errors import SlackApiError

from firefighter.incidents.forms.create_incident import CreateIncidentFormBase
from firefighter.incidents.forms.select_impact import SelectImpactForm
from firefighter.incidents.models.priority import Priority
from firefighter.jira_app.client import (
    JiraAPIError,
    JiraUserNotFoundError,
)
from firefighter.raid.client import client as jira_client
from firefighter.raid.messages import (
    SlackMessageRaidComment,
    SlackMessageRaidCreatedIssue,
    SlackMessageRaidModifiedIssue,
)
from firefighter.raid.models import FeatureTeam, JiraTicket, RaidArea
from firefighter.raid.service import (
    create_issue_customer,
    create_issue_documentation_request,
    create_issue_feature_request,
    create_issue_internal,
    create_issue_seller,
    get_jira_user_from_user,
)
from firefighter.raid.utils import get_domain_from_email
from firefighter.slack.models.conversation import Conversation

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from firefighter.incidents.models.impact import ImpactLevel
    from firefighter.incidents.models.user import User
    from firefighter.jira_app.models import JiraUser
    from firefighter.raid.types import JiraObject
    from firefighter.slack.messages.base import SlackMessageSurface

logger = logging.getLogger(__name__)
RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID


class PlatformChoices(models.TextChoices):
    FR = "platform-FR", ":fr: FR"
    DE = "platform-DE", ":de: DE"
    IT = "platform-IT", ":it: IT"
    ES = "platform-ES", ":es: ES"
    UK = "platform-UK", ":uk: UK"
    ALL = "platform-All", ":earth_africa: ALL"
    INTERNAL = "platform-Internal", ":logo-manomano: Internal"


def initial_priority() -> Priority:
    return Priority.objects.get(default=True)


class CreateNormalIncidentFormBase(CreateIncidentFormBase):
    platform = forms.ChoiceField(
        label="Platform",
        choices=PlatformChoices.choices,
    )
    title = forms.CharField(
        label="Title",
        max_length=128,
        min_length=10,
        widget=forms.TextInput(attrs={"placeholder": "What's going on?"}),
    )
    description = forms.CharField(
        label="Summary",
        min_length=10,
        max_length=1200,
    )
    suggested_team_routing = forms.ModelChoiceField(
        queryset=FeatureTeam.objects.only("name"),
        label="Feature Team or Train",
        required=True,
    )
    priority = forms.ModelChoiceField(
        label="Priority",
        queryset=Priority.objects.filter(enabled_create=True),
        initial=initial_priority,
        widget=forms.HiddenInput(),
    )

    field_order = [
        "area",
        "platform",
        "title",
        "description",
        "seller_contract_id",
        "is_key_account",
        "is_seller_in_golden_list",
        "zoho_desk_ticket_id",
        "zendesk_ticket_id",
        "suggested_team_routing",
    ]

    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError


class CreateNormalCustomerIncidentForm(CreateNormalIncidentFormBase):
    area = forms.ModelChoiceField(queryset=RaidArea.objects.filter(area="Customers"))
    zendesk_ticket_id = forms.CharField(
        label="Zendesk Ticket ID", max_length=128, min_length=2, required=False
    )

    # XXX business impact: infer from impact/add in impact modal?
    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Never,
        **kwargs: Never,
    ) -> None:
        jira_user: JiraUser = get_jira_user_from_user(creator)
        issue_data = create_issue_customer(
            title=self.cleaned_data["title"],
            description=self.cleaned_data["description"],
            priority=self.cleaned_data["priority"].value,
            reporter=jira_user.id,
            platform=self.cleaned_data["platform"],
            business_impact=str(get_business_impact(impacts_data)),
            team_to_be_routed=self.cleaned_data["suggested_team_routing"],
            area=self.cleaned_data["area"].name,
            zendesk_ticket_id=self.cleaned_data["zendesk_ticket_id"],
            labels=[""],
        )
        process_jira_issue(
            issue_data, creator, jira_user=jira_user, impacts_data=impacts_data
        )


class CreateRaidDocumentationRequestIncidentForm(CreateNormalIncidentFormBase):
    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Never,
        **kwargs: Never,
    ) -> None:
        jira_user: JiraUser = get_jira_user_from_user(creator)
        issue_data = create_issue_documentation_request(
            title=self.cleaned_data["title"],
            description=self.cleaned_data["description"],
            priority=self.cleaned_data["priority"].value,
            reporter=jira_user.id,
            platform=self.cleaned_data["platform"],
            labels=[""],
        )

        process_jira_issue(
            issue_data, creator, jira_user=jira_user, impacts_data=impacts_data
        )


class CreateRaidFeatureRequestIncidentForm(CreateNormalIncidentFormBase):
    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Never,
        **kwargs: Never,
    ) -> None:
        jira_user: JiraUser = get_jira_user_from_user(creator)
        issue_data = create_issue_feature_request(
            title=self.cleaned_data["title"],
            description=self.cleaned_data["description"],
            priority=self.cleaned_data["priority"].value,
            reporter=jira_user.id,
            platform=self.cleaned_data["platform"],
            labels=[""],
        )

        process_jira_issue(
            issue_data, creator, jira_user=jira_user, impacts_data=impacts_data
        )


class CreateRaidInternalIncidentForm(CreateNormalIncidentFormBase):
    area = forms.ModelChoiceField(
        queryset=RaidArea.objects.filter(area="Internal").order_by("name")
    )

    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Never,
        **kwargs: Never,
    ) -> None:
        jira_user: JiraUser = get_jira_user_from_user(creator)
        issue_data = create_issue_internal(
            title=self.cleaned_data["title"],
            description=self.cleaned_data["description"],
            priority=self.cleaned_data["priority"].value,
            reporter=jira_user.id,
            platform=self.cleaned_data["platform"],
            business_impact=str(get_business_impact(impacts_data)),
            team_to_be_routed=self.cleaned_data["suggested_team_routing"],
            area=self.cleaned_data["area"].name,
            labels=[""],
        )

        process_jira_issue(
            issue_data, creator, jira_user=jira_user, impacts_data=impacts_data
        )


class RaidCreateIncidentSellerForm(CreateNormalIncidentFormBase):
    area = forms.ModelChoiceField(queryset=RaidArea.objects.filter(area="Sellers"))
    seller_contract_id = forms.CharField(
        label="Seller Contract ID", max_length=128, min_length=0
    )
    is_key_account = forms.BooleanField(label="Is it a Key Account?", required=False)
    is_seller_in_golden_list = forms.BooleanField(
        label="Is the seller in the Golden List?", required=False
    )
    zoho_desk_ticket_id = forms.CharField(
        required=False, label="Zoho Desk Ticket ID", max_length=128, min_length=1
    )

    def trigger_incident_workflow(
        self,
        creator: User,
        impacts_data: dict[str, ImpactLevel],
        *args: Never,
        **kwargs: Never,
    ) -> None:
        jira_user: JiraUser = get_jira_user_from_user(creator)
        issue_data = create_issue_seller(
            title=self.cleaned_data["title"],
            description=self.cleaned_data["description"],
            priority=self.cleaned_data["priority"].value,
            reporter=jira_user.id,
            platform=self.cleaned_data["platform"],
            business_impact=str(get_business_impact(impacts_data)),
            team_to_be_routed=self.cleaned_data["suggested_team_routing"],
            area=self.cleaned_data["area"].name,
            zoho_desk_ticket_id=self.cleaned_data["zoho_desk_ticket_id"],
            is_key_account=self.cleaned_data["is_key_account"],
            is_seller_in_golden_list=self.cleaned_data["is_seller_in_golden_list"],
            seller_contract_id=self.cleaned_data["seller_contract_id"],
            labels=[""],
        )
        process_jira_issue(
            issue_data, creator, jira_user=jira_user, impacts_data=impacts_data
        )


def process_jira_issue(
    issue_data: JiraObject,
    user: User,
    jira_user: JiraUser,
    impacts_data: dict[str, ImpactLevel],
    *args: Never,
    **kwargs: Never,
) -> None:
    # XXX Deduplicate from these forms and from incident_created signal
    jira_ticket = JiraTicket.objects.create(**issue_data)
    impacts_form = SelectImpactForm(impacts_data)

    impacts_form.save(incident=jira_ticket)

    set_jira_ticket_watchers_raid(jira_ticket)
    alert_slack_new_jira_ticket(jira_ticket)


def set_jira_ticket_watchers_raid(jira_ticket: JiraTicket) -> None:
    issue_id = jira_ticket.id
    reporter = jira_ticket.reporter.id

    try:
        default_jira_user = jira_client.get_jira_user_from_jira_id(
            RAID_DEFAULT_JIRA_QRAFT_USER_ID
        )
    except JiraUserNotFoundError:
        logger.exception(
            f"Could not find Jira user with account id {RAID_DEFAULT_JIRA_QRAFT_USER_ID}"
        )
    try:
        jira_client.jira.add_watcher(issue=issue_id, watcher=reporter)
    except JiraAPIError:
        logger.exception(
            f"Could not add the watcher {jira_ticket.reporter.id} to the ticket {issue_id}"
        )
        try:
            jira_client.jira.remove_watcher(issue=issue_id, watcher=default_jira_user)

        except JiraAPIError:
            logger.exception(
                f"Could not add the watcher {jira_ticket.reporter.id} to the ticket {issue_id}"
            )


def alert_slack_new_jira_ticket(
    jira_ticket: JiraTicket,
    reporter_user: User | None = None,
    reporter_email: str | None = None,
) -> None:
    # These alerts are not for critical incidents
    if hasattr(jira_ticket, "incident") and jira_ticket.incident:
        raise ValueError("This is a critical incident, not a raid incident.")

    # Get the reporter's email and user from ticket if not provided
    reporter_user = reporter_user or jira_ticket.reporter.user
    reporter_email = reporter_email or reporter_user.email
    # Get the user's email domain (without @, without subdomain(s), with tld)
    user_domain: str = get_domain_from_email(reporter_email)

    if not reporter_user:
        logger.warning(f"Reporter user not found for Jira ticket {jira_ticket.id}.")
        return
    message = SlackMessageRaidCreatedIssue(jira_ticket, reporter_user=reporter_user)
    if (
        hasattr(reporter_user, "slack_user")
        and reporter_user.slack_user
        and reporter_user.slack_user.slack_id
    ):
        try:
            # XXX: Slack ID is posted in the message instead of Name
            reporter_user.slack_user.send_private_message(
                message,
                unfurl_links=False,
            )
        except SlackApiError:
            logger.exception(
                f"Couldn't send private message to reporter {reporter_user.slack_user}"
            )

    # Get the right channels from tags
    channels = get_internal_alert_conversations(jira_ticket)
    if user_domain:
        channels.union(get_partner_alert_conversations(user_domain))
    channels_list = list(channels)
    if len(channels_list) == 0:
        logger.warning(
            f"No channel to send notification for Jira ticket {jira_ticket.id}."
        )

    for channel in channels_list:
        try:
            channel.send_message_and_save(message)
        except SlackApiError:
            logger.exception(
                f"Couldn't send message to channel {channel} for ticket {jira_ticket.id}"
            )


def alert_slack_update_ticket(
    jira_ticket_id: int,
    jira_ticket_key: str,
    jira_author_name: str,
    jira_field_modified: str,
    jira_field_from: str,
    jira_field_to: str,
) -> bool:
    message = SlackMessageRaidModifiedIssue(
        jira_ticket_key=jira_ticket_key,
        jira_author_name=jira_author_name,
        jira_field_modified=jira_field_modified,
        jira_field_from=jira_field_from,
        jira_field_to=jira_field_to,
    )
    return send_message_to_watchers(jira_issue_id=jira_ticket_id, message=message)


def alert_slack_comment_ticket(
    webhook_event: str,
    jira_ticket_id: int,
    jira_ticket_key: str,
    author_jira_name: str,
    comment: str,
) -> bool:
    message: SlackMessageSurface = SlackMessageRaidComment(
        jira_ticket_key=jira_ticket_key,
        author_jira_name=author_jira_name,
        comment=comment,
        webhook_event=webhook_event,
    )
    return send_message_to_watchers(jira_issue_id=jira_ticket_id, message=message)


def send_message_to_watchers(
    jira_issue_id: int,
    message: SlackMessageSurface,
) -> bool:
    watchers = jira_client.get_watchers_from_jira_ticket(jira_issue_id)
    if not watchers:
        return True

    for watcher in watchers:
        try:
            watcher_account_id = watcher.get("accountId")
            if watcher_account_id is None:
                logger.warning(f"Couldn't find Jira account ID for watcher {watcher}")
                continue

            if watcher.get("accountType") == "app":
                logger.info(
                    f"Skipping sending message to jira_user_id={watcher_account_id}: is an app"
                )
                continue
            watcher_jira_user = jira_client.get_jira_user_from_jira_id(
                watcher_account_id
            )
            watcher_slack_user = (
                watcher_jira_user.user.slack_user
                if hasattr(watcher_jira_user.user, "slack_user")
                else None
            )
            if watcher_slack_user is None:
                logger.warning(
                    f"Couldn't find Slack user from Jira account ID for watcher {watcher}"
                )
                continue
            watcher_slack_user.send_private_message(
                message,
                unfurl_links=False,
            )
        except SlackApiError:
            logger.warning(
                f"Couldn't send private message to reporter with jira_id={watcher.get('accountId', watcher)}"
            )
    return True


def get_business_impact(impacts_data: dict[str, ImpactLevel]) -> str | None:
    impact_form = SelectImpactForm(impacts_data)
    return impact_form.business_impact_new


def get_partner_alert_conversations(user_domain: str) -> QuerySet[Conversation]:
    # Get the right channel from tags
    return Conversation.objects.filter(tag__contains=f"raid_alert__{user_domain}")


def get_internal_alert_conversations(jira_ticket: JiraTicket) -> QuerySet[Conversation]:
    impact_tag = "high" if jira_ticket.business_impact == "High" else "normal"
    project = "sbi" if jira_ticket.project_key == "SBI" else "incidents"
    return Conversation.objects.filter(
        tag__contains=f"raid_alert__{project}_{impact_tag}"
    )
