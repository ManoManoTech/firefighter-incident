from __future__ import annotations

from textwrap import shorten
from typing import TYPE_CHECKING, Any, Never
from urllib.parse import urljoin

from django.conf import settings
from django.urls import reverse
from slack_sdk.models.blocks.basic_components import (
    MarkdownTextObject,
    PlainTextObject,
    TextObject,
)
from slack_sdk.models.blocks.block_elements import ButtonElement, ImageElement
from slack_sdk.models.blocks.blocks import (
    ActionsBlock,
    Block,
    ContextBlock,
    DividerBlock,
    HeaderBlock,
    SectionBlock,
)
from slack_sdk.models.metadata import Metadata

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.impact import LevelChoices
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.incident_role_type import IncidentRoleType
from firefighter.slack.messages.base import (
    SectionBlockUpdateIntent,
    SlackMessageStrategy,
    SlackMessageSurface,
)
from firefighter.slack.models.message import Message
from firefighter.slack.slack_templating import (
    date_time,
    slack_block_quote,
    user_slack_handle_or_name,
)
from firefighter.slack.views.modals.close import CloseModal
from firefighter.slack.views.modals.downgrade_workflow import DowngradeWorkflowModal
from firefighter.slack.views.modals.trigger_oncall import OnCallModal
from firefighter.slack.views.modals.update import UpdateModal
from firefighter.slack.views.modals.update_roles import UpdateRolesModal
from firefighter.slack.views.modals.update_status import UpdateStatusModal

if TYPE_CHECKING:
    from collections.abc import Iterable

    from firefighter.incidents.models.incident import Incident
    from firefighter.incidents.models.incident_update import IncidentUpdate
    from firefighter.incidents.models.priority import Priority

POSTMORTEM_HELP_URL: str | None = settings.SLACK_POSTMORTEM_HELP_URL
EMERGENCY_COMMUNICATION_GUIDE_URL: str | None = (
    settings.SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL
)
SLACK_EMERGENCY_USERGROUP_ID: str | None = settings.SLACK_EMERGENCY_USERGROUP_ID
APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME
SLACK_APP_EMOJI: str = settings.SLACK_APP_EMOJI


def get_key_events_accessory(incident: Incident) -> dict[str, Any]:
    # ruff: noqa: PLC0415
    from firefighter.slack.views.modals.key_event_message import SlackMessageKeyEvents

    key_events_msg = Message.objects.get_or_none(
        ff_type=SlackMessageKeyEvents.id, conversation=incident.conversation
    )
    if key_events_msg:
        return {
            "accessory": ButtonElement(
                text="Update key events",
                url=str(key_events_msg.get_permalink),
                value=str(key_events_msg.get_permalink),
                action_id="open_link",
            ),
        }

    return {}


class SlackMessageIncidentPostMortemReminder(SlackMessageSurface):
    id = "ff_incident_postmortem_reminder"

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        super().__init__()

    def get_text(self) -> str:
        return f"Incident #{self.incident.id} {self.incident.status.label}! Don't forget to make a post-mortem."

    def get_blocks(self) -> list[Block]:
        accessory_kwargs = get_key_events_accessory(self.incident)
        blocks: list[Block] = [
            HeaderBlock(text=f":star:  Incident {self.incident.status.label}  :star:"),
            DividerBlock(),
            SectionBlock(text=" :zap: *Don't forget to edit the post-mortem* :zap:"),
            SectionBlock(
                text="<!here> The post-mortem is *required* to close an incident P2 and below.\nPlease update the incident as you move in the post-mortem process, to keep track of incidents and avoid similar ones in the future. "
            ),
            DividerBlock(),
            SectionBlock(text=":arrow_down:  *Post-mortem process*  :arrow_down: "),
            SectionBlock(
                text=f'1. When ready, update the incident status to "{IncidentStatus.POST_MORTEM.label}"',
                accessory=ButtonElement(
                    text="Update incident status",
                    value=str(self.incident.id),
                    action_id=UpdateStatusModal.open_action,
                ),
            ),
            SectionBlock(
                text="2. Edit your post-mortem on Confluence",
                accessory=ButtonElement(
                    text="Edit post-mortem",
                    value=self.incident.postmortem_for.page_edit_url,
                    url=self.incident.postmortem_for.page_edit_url,
                    action_id="open_link",
                ),
            ),
            SectionBlock(
                text=f"3. Submit the key events to {APP_DISPLAY_NAME}",
                **accessory_kwargs,
            ),
            SectionBlock(
                text="4. Once everything has been submitted, close the incident",
                accessory=ButtonElement(
                    text="Close incident",
                    value=str(self.incident.id),
                    action_id=CloseModal.open_action,
                ),
            ),
            DividerBlock(),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=":bulb: Updating the status and creating a post-mortem is crucial for the Platform Operations Report presented during the Tech Weekly."
                    )
                ]
            ),
        ]
        if POSTMORTEM_HELP_URL:
            blocks.insert(
                4,
                SectionBlock(
                    text='Need guidance on how to create a post-mortem? See our presentation "PostMortems // How to run them after incidents?"',
                    accessory=ButtonElement(
                        text="Open presentation",
                        url=POSTMORTEM_HELP_URL,
                        value=POSTMORTEM_HELP_URL,
                        action_id="open_link",
                    ),
                ),
            )
        return blocks


class SlackMessageIncidentFixedNextActions(SlackMessageSurface):
    id = "ff_incident_fixed_next_actions"

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        super().__init__()

    def get_text(self) -> str:
        return f"Incident #{self.incident.id} {self.incident.status.label}!"

    def get_blocks(self) -> list[Block]:
        accessory_kwargs = get_key_events_accessory(self.incident)
        blocks: list[Block] = [
            HeaderBlock(text=f":star:  Incident {self.incident.status.label}  :star:"),
            DividerBlock(),
            SectionBlock(text=":arrow_down:  *Next actions*  :arrow_down: "),
            SectionBlock(
                text=f"1. Submit the key events to {APP_DISPLAY_NAME}",
                **accessory_kwargs,
            ),
            SectionBlock(
                text="2. Once all key metrics have been submitted, close the incident",
                accessory=ButtonElement(
                    text="Close incident",
                    value=str(self.incident.id),
                    action_id=CloseModal.open_action,
                ),
            ),
            DividerBlock(),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text="A post-mortem is *not* required for this incident.\nIf you want to create one, use `/incident postmortem` to create a new post-mortem page on Confluence."
                    )
                ]
            ),
        ]
        return blocks


class SlackMessageIncidentDeclaredAnnouncement(SlackMessageSurface):
    id = "ff_incident_declared"
    incident: Incident
    strategy: SlackMessageStrategy = SlackMessageStrategy.UPDATE

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        super().__init__()

    def get_text(self) -> str:
        return f"A new {self.incident.priority} incident has been declared: {self.incident.title}"

    def get_blocks(self) -> list[Block]:
        fields = [
            f"{self.incident.priority.emoji} *Priority:* {self.incident.priority.name}",
            f":package: *Incident category:* {self.incident.incident_category.name}",
            f":speaking_head_in_silhouette: *Opened by:* {user_slack_handle_or_name(self.incident.created_by)}",
            f":calendar: *Created at:* {date_time(self.incident.created_at)}",
            f"{SLACK_APP_EMOJI} <{self.incident.status_page_url + '?utm_medium=FireFighter+Slack&utm_source=Slack+Message&utm_campaign=Announcement+Message+In+Channel'}|*{APP_DISPLAY_NAME} Status Page*>",
        ]
        if hasattr(self.incident, "jira_ticket") and self.incident.jira_ticket:
            fields.append(f":jira_new: <{self.incident.jira_ticket.url}|*Jira ticket*>")

        # Add custom fields if present
        if hasattr(self.incident, "custom_fields") and self.incident.custom_fields:
            custom_fields = self.incident.custom_fields
            if custom_fields.get("zendesk_ticket_id"):
                fields.append(f":ticket: *Zendesk Ticket:* {custom_fields['zendesk_ticket_id']}")
            if custom_fields.get("seller_contract_id"):
                fields.append(f":memo: *Seller Contract:* {custom_fields['seller_contract_id']}")
            if custom_fields.get("zoho_desk_ticket_id"):
                fields.append(f":ticket: *Zoho Desk Ticket:* {custom_fields['zoho_desk_ticket_id']}")
            if custom_fields.get("is_key_account") is True:
                fields.append(":star: *Key Account*")
            if custom_fields.get("is_seller_in_golden_list") is True:
                fields.append(":medal: *Golden List Seller*")

        blocks: list[Block] = [
            SectionBlock(
                text=f"{self.incident.priority.emoji} {self.incident.priority.name} - A new incident has been declared:"
            ),
            SectionBlock(text=f"*{shorten(self.incident.title, 2995)}*"),
            slack_block_quote(self.incident.description),
            DividerBlock(),
            SectionBlock(
                fields=fields,
                accessory=ButtonElement(
                    text="Update",
                    value=str(self.incident.id),
                    action_id=UpdateModal.open_action,
                ),
            ),
            *self._impact_blocks(),
        ]
        return blocks

    def _impact_blocks(self) -> list[Block]:
        impacts = self.incident.impacts.all().order_by("impact_level__value")[:10]
        none_level = LevelChoices.NONE.value
        fields = [
            f"{impact.impact_type.emoji} *{impact.impact_type.name}*: {impact.impact_level.emoji if impact.impact_level.value != none_level else ''} {impact.impact_level.value_label}"
            for impact in impacts
        ]
        if len(fields) == 0:
            return [DividerBlock()]
        return [
            DividerBlock(),
            SectionBlock(fields=fields),
        ]


class SlackMessageIncidentDeclaredAnnouncementGeneral(SlackMessageSurface):
    id = "ff_general_incident_declared"
    incident: Incident

    def __init__(self, incident: Incident) -> None:
        """The message to post in general incident channel (tag=tech_incidents) when an incident is opened.

        Args:
            incident (Incident): Your incident
        """
        self.incident = incident
        super().__init__()

    def get_text(self) -> str:
        return f"A new {self.incident.priority} incident #{self.incident.id} has been declared: {self.incident.title}"

    def get_blocks(self) -> list[Block]:
        fields = [
            f"{self.incident.priority.emoji} *Priority:* {self.incident.priority.name}",
            f":package: *Incident category:* {self.incident.incident_category.name}",
            f"{SLACK_APP_EMOJI} <{self.incident.status_page_url + '?utm_medium=FireFighter+Slack&utm_source=Slack+Message&utm_campaign=Announcement+Message+General'}|*{APP_DISPLAY_NAME} Status Page*>",
            f":speaking_head_in_silhouette: *Opened by:* {user_slack_handle_or_name(self.incident.created_by)}",
            f":calendar: *Created at:* {date_time(self.incident.created_at)}",
        ]
        if hasattr(self.incident, "jira_ticket") and self.incident.jira_ticket:
            fields.append(f":jira_new: <{self.incident.jira_ticket.url}|*Jira ticket*>")
        blocks: list[Block] = [
            SectionBlock(
                text=f"{self.incident.priority.emoji} {self.incident.priority.name} - A new incident has been declared in #{self.incident.slack_channel_name}."
            ),
            SectionBlock(
                text=f"*{shorten(self.incident.title, 2995, placeholder='...')}*"
            ),
            slack_block_quote(self.incident.description),
            DividerBlock(),
            SectionBlock(fields=fields),
        ]

        return blocks


class SlackMessageIncidentRolesUpdated(SlackMessageSurface):
    """The message to post in the incident channel when the roles are updated.

    Args:
        incident (Incident): Your incident.
        incident_update (IncidentUpdate): The opening incident update.
        first_update (bool): Whether this is the first update of the incident. Defaults to False.
        updated_fields (list[str]): The fields that were updated. Defaults to None.
    """

    id = "ff_incident_roles_updated"

    incident: Incident
    incident_update: IncidentUpdate | None

    def __init__(
        self,
        incident: Incident,
        incident_update: IncidentUpdate | None,
        *,
        first_update: bool = False,
        updated_fields: list[str] | None = None,
    ) -> None:
        self.incident = incident
        self.incident_update = incident_update
        self.first_update = first_update
        self.updated_fields = updated_fields
        self._new_roles = self._get_updated_roles()
        super().__init__()

    def get_text(self) -> str:
        roles_text = [
            f"{role.role_type.name}: {user_slack_handle_or_name(role.user if hasattr(role, 'user') else None)}"
            for role in self._new_roles
        ]
        return f"Roles updated. {roles_text}. Updated by: {user_slack_handle_or_name(self.incident_update.created_by if self.incident_update else self.incident.created_by)}."

    def get_metadata(self) -> Metadata:
        return Metadata(
            event_type=self.id,
            event_payload={
                "ff_type": self.id,
                "incident_id": self.incident.id,
                "incident_update_id": (
                    str(self.incident_update.id) if self.incident_update else None
                ),
                "new_roles": {
                    role.role_type.slug: user_slack_handle_or_name(
                        role.user if hasattr(role, "user") else None
                    )
                    for role in self._new_roles
                },
            },
        )

    def get_blocks(self) -> list[Block]:
        blocks: list[Block] = []
        if not self.first_update:
            blocks.append(SectionBlock(text="_Roles updated._"))

        fields = [
            f"{role.role_type.emoji} *{role.role_type.name}:*\n{user_slack_handle_or_name(role.user if hasattr(role, 'user') else None)}"
            for role in self._new_roles
        ]
        if len(fields) == 0:
            fields.append("_No changes detected._")

        blocks.extend(
            [
                DividerBlock(),
                SectionBlock(
                    block_id="message_role_update",
                    fields=fields,
                    accessory=ButtonElement(
                        text="Update",
                        value=str(self.incident.id),
                        action_id=UpdateRolesModal.open_action,
                    ),
                ),
            ]
        )
        if not self.first_update:
            blocks.append(
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text=f":speaking_head_in_silhouette: *Updated by:* {user_slack_handle_or_name(self.incident_update.created_by if self.incident_update else self.incident.created_by)}",
                        )
                    ]
                )
            )

        return blocks

    def _get_updated_roles(self) -> Iterable[IncidentRole]:
        if self.updated_fields is None and not self.first_update:
            return []

        incident_roles: list[IncidentRole] = []

        role_types_queryset = IncidentRoleType.objects.all()
        if self.first_update:
            role_types_queryset = role_types_queryset.filter(required=True)
        if not self.first_update and self.updated_fields is not None:
            role_types_queryset = role_types_queryset.filter(
                slug__in=[
                    updated_field.removesuffix("_id")
                    for updated_field in self.updated_fields
                ]
            )
        # XXX Smelly
        for incident_role_type in role_types_queryset:
            # Get the IncidentRole if it exists in DB, or create it locally with User=None
            try:
                incident_role = IncidentRole.objects.select_related(
                    "user", "user__slack_user"
                ).get(incident=self.incident, role_type=incident_role_type)
            except IncidentRole.DoesNotExist:
                incident_role = IncidentRole(
                    incident=self.incident, role_type=incident_role_type, user=None
                )
            incident_roles.append(incident_role)
        return incident_roles


class SlackMessageIncidentStatusUpdated(SlackMessageSurface):
    id = "ff_incident_status_updated"
    incident: Incident
    incident_update: IncidentUpdate

    in_channel: bool = True
    title_text: str | None = None

    def __init__(
        self,
        incident: Incident,
        incident_update: IncidentUpdate,
        *args: Never,
        in_channel: bool = True,
        status_changed: bool = False,
        old_priority: Priority | None = None,
        **kwargs: Never,
    ) -> None:
        self.incident = incident
        self.incident_update = incident_update
        self.in_channel = in_channel

        if self.in_channel:
            self.title_text = "A new incident update has been posted"
        elif incident.status == IncidentStatus.MITIGATED and status_changed:
            self.title_text = f":large_green_circle:  Incident #{incident.slack_channel_name} has been {incident.status.label}.  :large_green_circle:"
        elif old_priority is not None and old_priority.value > 3:
            self.title_text = f"Incident #{incident.slack_channel_name} has escalated from {old_priority.name} to {incident.priority.name}."
        else:
            self.title_text = (
                f"Incident #{incident.slack_channel_name} has received an update."
            )
        super().__init__()

    def get_blocks(self) -> list[Block]:
        blocks: list[Block] = [SectionBlock(text=self.title_text)]

        if self.incident_update.message and self.incident_update.message != "":
            blocks.append(
                slack_block_quote(self.incident_update.message),
            )
        if self.incident_update.title and self.incident_update.title != "":
            blocks.append(
                SectionBlock(
                    text=f"New title: *{shorten(self.incident_update.title, 2985)}*"
                ),
            )
        if self.incident_update.description and self.incident_update.description != "":
            blocks.append(
                slack_block_quote(self.incident_update.description),
            )
        fields = []
        if self.in_channel:
            if self.incident_update.status:
                fields.append(
                    MarkdownTextObject(
                        text=f":information_source: *Status:* {self.incident.status.label}"
                    )
                )
            if self.incident_update.priority:
                fields.append(
                    MarkdownTextObject(
                        text=f":rotating_light: *Priority:* {self.incident.priority.emoji} {self.incident.priority.name}"
                    )
                )
            if self.incident_update.incident_category:
                fields.append(
                    MarkdownTextObject(
                        text=f":package: *Incident category:* {self.incident.incident_category.group.name} - {self.incident.incident_category.name}"
                    )
                )
            if self.incident_update.environment:
                fields.append(
                    MarkdownTextObject(
                        text=f":round_pushpin: *Environment:* {self.incident_update.environment.value}"
                    )
                )

        if len(fields) > 0:
            blocks.extend(
                [
                    DividerBlock(),
                    SectionBlock(
                        block_id="message_status_update",
                        fields=fields,
                        accessory=(
                            ButtonElement(
                                text="Update",
                                value=str(self.incident.id),
                                action_id=UpdateStatusModal.open_action,
                            )
                            if self.in_channel and self.incident.status != IncidentStatus.CLOSED
                            else None
                        ),
                    ),
                ]
            )

        if self.incident_update.created_by:
            blocks.append(
                ContextBlock(
                    elements=[
                        TextObject(
                            type="mrkdwn",
                            text=f":speaking_head_in_silhouette: *Posted by:* {user_slack_handle_or_name(self.incident_update.created_by)}",
                        )
                    ]
                )
            )
        return blocks

    def get_metadata(self) -> Metadata:
        return Metadata(
            event_type=self.id,
            event_payload={
                "incident_id": self.incident.id,
                "incident_update_id": str(self.incident_update.id),
            },
        )

    def get_text(self) -> str:
        return f"Incident #{self.incident.id} has received an update."

    def get_slack_message_options(
        self, *args: Never, **kwargs: Never
    ) -> dict[str, bool]:
        return {
            "unfurl_links": False,
        }


class SlackMessageIncidentPostMortemCreated(SlackMessageSurface):
    id = "ff_incident_postmortem_created"
    incident: Incident

    def __init__(self, incident: Incident) -> None:
        self.incident = incident
        super().__init__()

    def get_text(self) -> str:
        return f"📔 The post-mortem has been created, you can edit it here: {self.incident.postmortem_for.page_url}."

    def get_blocks(self) -> list[Block]:
        return [SectionBlock(text=self.get_text())]


class SlackMessageIncidentDuringOffHours(SlackMessageSurface):
    id = "ff_incident_during_off_hours"

    def get_text(self) -> str:
        return "We are out of office hours. If you need it, you can trigger an on-call response with `/incident oncall`."

    def get_blocks(self) -> list[Block]:
        oncall_url = urljoin(settings.BASE_URL, reverse("pagerduty:oncall-list"))
        return [
            SectionBlock(
                text=f":palm_tree: *Incident during out of office hours* :palm_tree: \nIf you need help, you can trigger an on-call that will call the person in charge in the gear.\n_You can also see current on-call people and their escalation on <{oncall_url}|this page>._",
                accessory=ImageElement(
                    image_url="https://freesvg.org/img/phone-call-icon.png",
                    alt_text="phone icon",
                ),
            ),
            ContextBlock(
                elements=[
                    TextObject(
                        type="mrkdwn",
                        text=":bulb: _You can also access the on-call menu with `/incident oncall`, on any incident_",
                    )
                ]
            ),
            ActionsBlock(
                elements=[
                    ButtonElement(
                        text=TextObject(
                            type="plain_text",
                            text=":phone: Select on-call gear",
                            emoji=True,
                        ),
                        action_id=OnCallModal.open_action,
                        style="primary",
                    ),
                    ButtonElement(
                        text=TextObject(
                            type="plain_text",
                            text=":confluence: See on-call & escalation",
                            emoji=True,
                        ),
                        action_id="open_link",
                        url=oncall_url,
                    ),
                ]
            ),
        ]


class SlackMessageIncidentUpdateReminder(SlackMessageSurface):
    id = "ff_incident_update_reminder"

    def __init__(self, incident: Incident, time_delta_fmt: str):
        self.incident = incident
        self.time_delta_fmt = time_delta_fmt
        super().__init__()

    def get_blocks(self) -> list[Block]:
        if self.incident.priority.value >= 4:
            text = f"It is a {self.incident.priority.name} incident with no update for {self.time_delta_fmt}. You may want to update this incident."
        else:
            text = f"It is a {self.incident.priority.name} incident and a lot of people, customers and employees, are probably impacted. This incident has no update for {self.time_delta_fmt}. You need to update this incident to broadcast information in #tech-incidents."

        return [
            HeaderBlock(
                text=PlainTextObject(
                    text=":robot_face: Reminder to update this incident :robot_face:",
                    emoji=True,
                )
            ),
            SectionBlock(text=MarkdownTextObject(text=text)),
            SectionBlockUpdateIntent(self.incident),
        ]

    def get_text(self) -> str:
        return "Reminder to update this incident :)"


class SlackMessageIncidentComProcess(SlackMessageSurface):
    id = "ff_incident_com_process"
    incident: Incident

    def __init__(self, incident: Incident):
        self.incident = incident
        super().__init__()

    def get_blocks(self) -> list[Block]:
        mention_emergency_process = (
            f"\n\n:arrow_right: <{EMERGENCY_COMMUNICATION_GUIDE_URL}|COM PROCESS> "
            if SLACK_EMERGENCY_USERGROUP_ID
            else ""
        )
        mention_usergroup = (
            f":arrow_left:\n\n :loudspeaker: <!subteam^{SLACK_EMERGENCY_USERGROUP_ID}> *must* be informed."
            if SLACK_EMERGENCY_USERGROUP_ID
            else ""
        )
        return [
            HeaderBlock(
                text=PlainTextObject(
                    text=":robot_face: Emergency communication :robot_face:", emoji=True
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"As a {self.incident.priority.name} incident, it may drastically impact our customers for hours. If so, we created a emergency procedure to communicate with them.{mention_emergency_process}{mention_usergroup}"
                )
            ),
        ]

    def get_text(self) -> str:
        return f"Follow the communication process for {self.incident.priority.name} incidents."


class SlackMessageDeployWarning(SlackMessageSurface):
    id = "ff_deploy_warning"
    incident: Incident
    strategy: SlackMessageStrategy = SlackMessageStrategy.REPLACE

    def __init__(self, incident: Incident):
        self.incident = incident
        super().__init__()

    def get_blocks(self) -> list[Block]:
        blocks = [
            HeaderBlock(
                text=PlainTextObject(
                    text=f":warning: Deploy warning {'(Mitigated) ' if self.incident.status == IncidentStatus.MITIGATED else ''}:warning:",
                    emoji=True,
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"\nWe currently have a {self.incident.priority} {APP_DISPLAY_NAME} incident in our platform (#{self.incident.conversation.name}), refrain to deploy until it's resolved\n"
                )
            ),
        ]

        if self.incident.status >= IncidentStatus.MITIGATED:
            blocks.extend(
                [
                    SectionBlock(
                        text=MarkdownTextObject(
                            text=f":white_check_mark: *UPDATE*: Incident #{self.incident.conversation.name} has been mitigated, you can resume your deployments."
                        )
                    )
                ]
            )
        return blocks

    def get_text(self) -> str:
        return f"Warning: We have a {self.incident.priority} {APP_DISPLAY_NAME} incident in our platform, refrain to deploy until it's resolved"


class SlackMessagesSOS(SlackMessageSurface):
    id = "ff_sos"

    def __init__(self, incident: Incident, usergroup: str):
        self.incident = incident
        self.usergroup_target = usergroup
        super().__init__()

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"{SLACK_APP_EMOJI} *We need help on incident #{self.incident.conversation.name}* _incident:firefighter:"
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"Hello {self.usergroup_target}\nIncident responders have asked for help on a critical incident. This incident is a *{self.incident.priority.name}* and concerns the *{self.incident.incident_category.group.name}/{self.incident.incident_category}* domain.\n\nPlease help the team working to mitigate it :lovecommunity:"
                )
            ),
        ]

    def get_text(self) -> str:
        return f"Hello {self.usergroup_target}, we need your help on {self.incident.priority.name} incident {self.incident.conversation.name}."


class SlackMessageRoleAssignedToYou(SlackMessageSurface):
    id = "ff_role_assigned_to_you"

    def __init__(
        self,
        incident: Incident,
        role_type: IncidentRoleType,
        *,
        first_update: bool = False,
    ):
        self.incident = incident
        self.role_type: IncidentRoleType = role_type
        self.first_update: bool = first_update
        super().__init__()

    def get_blocks(self) -> list[Block]:
        context_elements = [
            MarkdownTextObject(
                text=f":link: <{self.role_type.url}|More information and guidance about the {self.role_type.name.lower()} role>"
            ),
        ]
        if self.first_update and self.role_type.required:
            context_elements.append(
                MarkdownTextObject(
                    text=":bulb: _You have been assigned this role automatically because you created the incident. You can reassign this role to someone else if you want._"
                )
            )
        return [
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"{SLACK_APP_EMOJI} *Incident #{self.incident.conversation.name}*:"
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"*{self.role_type.emoji} You have been assigned the {self.role_type.name} role*"
                )
            ),
            slack_block_quote(self.role_type.summary),
            ContextBlock(elements=context_elements),
        ]

    def get_text(self) -> str:
        return f"You have been assigned the {self.role_type.name} role on incident #{self.incident.conversation.name}."


class SlackMessageIncidentDowngradeHint(SlackMessageSurface):
    id = "ff_incident_downgrade_hint"

    def __init__(self, incident: Incident, incident_update: IncidentUpdate) -> None:
        self.incident = incident
        self.incident_update = incident_update
        super().__init__()

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"{SLACK_APP_EMOJI} *Incident #{self.incident.conversation.name}*:"
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text=f"The incident was updated to a {self.incident.priority.name} priority."
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text="You may choose to use the Jira-ticket based workflow instead of the Slack channel one."
                )
            ),
            SectionBlock(
                text=MarkdownTextObject(
                    text="Do to so, click the button. After confirmation, it will close the incident channel, but keep the Jira ticket open."
                ),
                accessory=ButtonElement(
                    text="Change workflow",
                    action_id=DowngradeWorkflowModal.open_action,
                    value=str(self.incident.id),
                ),
            ),
            ContextBlock(
                elements=[
                    MarkdownTextObject(
                        text=f":bulb: You can change to a normal workflow with `{settings.SLACK_INCIDENT_COMMAND} downgrade`"
                    )
                ]
            ),
        ]

    def get_text(self) -> str:
        return f"Incident #{self.incident.id} might not need an incident channel, as it is {self.incident.priority.name}."
