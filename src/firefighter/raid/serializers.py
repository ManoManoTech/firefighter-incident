from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from rest_framework import serializers

from firefighter.incidents.models.user import User
from firefighter.jira_app.client import (
    JiraAPIError,
    JiraUserNotFoundError,
    SlackNotificationError,
)
from firefighter.raid.client import client as jira_client
from firefighter.raid.forms import (
    alert_slack_comment_ticket,
    alert_slack_new_jira_ticket,
    alert_slack_update_ticket,
)
from firefighter.raid.models import JiraTicket
from firefighter.raid.utils import get_domain_from_email
from firefighter.slack.models.user import SlackUser

if TYPE_CHECKING:
    from firefighter.jira_app.models import JiraUser


JIRA_USER_IDS: dict[str, str] = settings.RAID_JIRA_USER_IDS

logger = logging.getLogger(__name__)


class IgnoreEmptyStringListField(serializers.ListField):
    def to_internal_value(self, data: list[Any] | Any) -> list[str]:
        # Check if data is a list
        if not isinstance(data, list):
            msg = f'Expected a list but got type "{type(data).__name__}".'
            raise serializers.ValidationError(msg)

        # Filter out any empty string values
        data = [item for item in data if item != ""]

        return super().to_internal_value(data)


def validate_no_spaces(value: str) -> None:
    """Ensure the string does not contain spaces."""
    if " " in value:
        raise serializers.ValidationError("The string cannot contain spaces.")


def get_reporter_user_from_email(reporter_email: str) -> tuple[User, JiraUser, str]:
    user_domain: str = get_domain_from_email(reporter_email)
    try:
        reporter_user: User = User.objects.get(email=reporter_email)
        reporter = jira_client.get_jira_user_from_user(reporter_user)
    except (User.DoesNotExist, JiraUserNotFoundError):
        reporter_user_tmp = SlackUser.objects.upsert_by_email(email=reporter_email)
        if reporter_user_tmp is not None:
            reporter_user = reporter_user_tmp

        logger.warning(
            f"Reporter email {reporter_email} not found in Jira. Using default user."
        )

        # Get default Jira user, depending on the domain
        # We might have accounts with Slack users, but not Jira users
        # In that case, we use the default Jira user for that domain
        match JIRA_USER_IDS.get(user_domain):
            case jira_user_id if jira_user_id is not None:
                reporter = jira_client.get_jira_user_from_jira_id(jira_user_id)
                reporter_user = (
                    reporter.user if reporter_user_tmp is None else reporter_user_tmp
                )
            case _:
                reporter = jira_client.get_jira_user_from_jira_id(
                    settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID
                )
                reporter_user = (
                    reporter.user if reporter_user_tmp is None else reporter_user_tmp
                )
    return reporter_user, reporter, user_domain


class LandbotIssueRequestSerializer(serializers.ModelSerializer[JiraTicket]):
    id = serializers.IntegerField(read_only=True)
    key = serializers.CharField(read_only=True)
    seller_contract_id = serializers.CharField(
        max_length=128,
        write_only=True,
        allow_null=True,
        allow_blank=True,
    )
    zoho = serializers.CharField(
        max_length=256,
        write_only=True,
        allow_null=True,
        allow_blank=True,
    )
    platform = serializers.ChoiceField(
        write_only=True, choices=["ES", "IT", "FR", "UK", "DE", "All", "Internal"]
    )
    reporter_email = serializers.EmailField(write_only=True)

    labels = serializers.ListField(
        required=False,
        write_only=True,
        child=serializers.CharField(
            max_length=128,
            allow_blank=False,
            allow_null=False,
            validators=[validate_no_spaces],
        ),
        help_text="List of labels to be added to the ticket. Labels cannot contain spaces and must not exceed 255 characters.",
    )
    incident_category = serializers.CharField(
        max_length=128,
        write_only=True,
        allow_null=True,
        allow_blank=True,
    )
    suggested_team_routing = serializers.CharField(max_length=10, write_only=True)
    project = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default="SBI",
        choices=[
            "SBI",
        ],
    )
    priority = serializers.IntegerField(
        min_value=1, max_value=5, write_only=True, allow_null=True,
        help_text="Priority level 1-5 (1=Critical, 2=High, 3=Medium, 4=Low, 5=Lowest)"
    )
    business_impact = serializers.ChoiceField(
        write_only=True, choices=["High", "Medium", "Low"], allow_null=True
    )
    environments = serializers.ListField(
        write_only=True,
        allow_null=True,
        default=["-"],
        child=serializers.ChoiceField(
            allow_null=True,
            allow_blank=True,
            choices=["INT", "STG", "PRD", "SUPPORT", "-"],
        ),
    )
    attachments = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    issue_type = serializers.ChoiceField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default="Incident",
        choices=[
            "Incident",
            "Service Request",
            "Documentation/Process Request",
            "Feature Request",
        ],
    )

    def validate_environments(self, value: list[str] | None) -> list[str] | Any:
        if not value:
            return self.fields["environments"].default
        return value

    def create(self, validated_data: dict[str, Any]) -> JiraTicket:
        reporter_email: str = validated_data["reporter_email"]

        reporter_user, reporter, user_domain = get_reporter_user_from_email(
            reporter_email
        )
        user_in_description: str = (
            f"\nReporter email {reporter_email}\n"
            if "manomano" not in user_domain
            else ""
        )

        issue = jira_client.create_issue(
            issuetype=validated_data["issue_type"],
            summary=validated_data["summary"],
            description=f"""{validated_data.get("description")}\n
\n
🤖 This ticket was created through the Incident Verification Bot https://landbot.pro/v3/H-1332620-8BF395J9STSHL7IN/index.html.\n
\n
{user_in_description}
\n
""",
            assignee=None,
            reporter=reporter.id,
            labels=validated_data["labels"],
            priority=validated_data["priority"],
            seller_contract_id=validated_data["seller_contract_id"],
            zoho_desk_ticket_id=validated_data["zoho"],
            platform=validated_data["platform"],
            incident_category=validated_data["incident_category"],
            business_impact=validated_data["business_impact"],
            environments=validated_data["environments"],
            suggested_team_routing=validated_data["suggested_team_routing"],
            project=validated_data["project"],
        )
        issue_id = issue.get("id")
        if issue_id is None:
            logger.error("Could not create Jira ticket")
            raise JiraAPIError("Could not create Jira ticket")
        if validated_data["attachments"] is not None:
            #  Prepare attachments and double check we don't have any empty strings
            attachments: list[str] = [
                a
                for a in validated_data["attachments"]
                .replace("[", "")
                .replace("]", "")
                .replace("'", "")
                .split(", ")
                if a
            ]
            jira_client.add_attachments_to_issue(issue_id, attachments)

        jira_ticket = JiraTicket.objects.create(**issue)

        # Send messages in the relevant Slack channels if needed and alert the reporter in DMs
        alert_slack_new_jira_ticket(
            jira_ticket, reporter_user=reporter_user, reporter_email=reporter_email
        )

        return jira_ticket

    class Meta:
        model = JiraTicket
        fields = [
            "summary",
            "description",
            "seller_contract_id",
            "zoho",
            "platform",
            "reporter_email",
            "incident_category",
            "labels",
            "environments",
            "issue_type",
            "business_impact",
            "priority",
            "id",
            "key",
            "attachments",
            "suggested_team_routing",
            "project",
        ]


class JiraWebhookUpdateSerializer(serializers.Serializer[Any]):
    issue = serializers.DictField()
    changelog = serializers.DictField()
    user = serializers.DictField()
    webhookEvent = serializers.ChoiceField(  # noqa: N815
        write_only=True,
        choices=["jira:issue_updated"],
    )

    def create(self, validated_data: dict[str, Any]) -> bool:
        jira_field_modified = validated_data["changelog"].get("items")[0].get("field")
        if jira_field_modified in {
            "Priority",
            "project",
            "description",
            "status",
        }:
            jira_ticket_key = validated_data["issue"].get("key")
            status = alert_slack_update_ticket(
                jira_ticket_id=validated_data["issue"].get("id"),
                jira_ticket_key=jira_ticket_key,
                jira_author_name=validated_data["user"].get("displayName"),
                jira_field_modified=jira_field_modified,
                jira_field_from=validated_data["changelog"]
                .get("items")[0]
                .get("fromString"),
                jira_field_to=validated_data["changelog"]
                .get("items")[0]
                .get("toString"),
            )
            if status is not True:
                logger.error(
                    f"Could not alert in Slack for the update/s in the Jira ticket {jira_ticket_key}"
                )
                raise SlackNotificationError("Could not alert in Slack")

        return True

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError


class JiraWebhookCommentSerializer(serializers.Serializer[Any]):
    issue = serializers.DictField()
    comment = serializers.DictField()
    webhookEvent = serializers.ChoiceField(  # noqa: N815
        write_only=True,
        choices=["comment_created", "comment_updated", "comment_deleted"],
    )

    def create(self, validated_data: dict[str, Any]) -> bool:
        jira_ticket_key = validated_data["issue"].get("key")
        status = alert_slack_comment_ticket(
            webhook_event=validated_data["webhookEvent"],
            jira_ticket_id=validated_data["issue"].get("id"),
            jira_ticket_key=jira_ticket_key,
            author_jira_name=validated_data["comment"].get("author").get("displayName"),
            comment=validated_data["comment"].get("body"),
        )
        if status is not True:
            logger.error(
                f"Could not alert in Slack for created/modified comment in the Jira ticket {jira_ticket_key}"
            )
            raise SlackNotificationError("Could not alert in Slack")
        return True

    def update(self, instance: Any, validated_data: Any) -> Any:
        raise NotImplementedError
