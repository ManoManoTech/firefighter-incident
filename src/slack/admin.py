from __future__ import annotations

from time import sleep
from typing import TYPE_CHECKING, Any

from django.contrib import admin, messages
from django.contrib.admin.decorators import action
from django.contrib.messages import constants
from django.contrib.messages.constants import ERROR, SUCCESS
from django.urls import reverse
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from slack_sdk.errors import SlackApiError

import incidents.admin
from slack.models import Message, SlackUser
from slack.models.conversation import Conversation
from slack.models.incident_channel import IncidentChannel
from slack.models.sos import Sos
from slack.models.user_group import UserGroup
from slack.tasks.fetch_conversations_members import (
    fetch_conversations_members_from_slack,
)
from slack.tasks.update_usergroups_members import update_usergroups_members_from_slack

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django.forms.models import ModelForm
    from django.http.request import HttpRequest

    from incidents.models import Incident


@admin.register(SlackUser)
class SlackUserAdmin(admin.ModelAdmin[SlackUser]):
    model = SlackUser
    list_display = ["user", "slack_id"]
    list_display_links = ["user", "slack_id"]
    list_max_show_all = 500
    autocomplete_fields = ["user"]
    list_filter = ["user__is_active"]

    @admin.action(description="Update info from Slack")
    def update_info(self, request: HttpRequest, queryset: QuerySet[SlackUser]) -> None:
        for slack_user in queryset:
            slack_user.update_user_info()
            sleep(0.5)
        self.message_user(
            request,
            ngettext(
                "Updated info for %d Slack user.",
                "Updated info for %d Slack users.",
                len(queryset),
            )
            % len(queryset),
            SUCCESS,
        )

    actions = [update_info]
    search_fields = ["user__username", "user__email", "slack_id"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin[Conversation]):
    model = Conversation
    list_display = [
        "name",
        "channel_id",
        "_type",
        "_status",
        "is_shared",
        "tag",
    ]
    list_display_links = [
        "name",
        "channel_id",
    ]
    list_max_show_all = 500
    search_fields = ["channel_id", "name", "tag"]

    autocomplete_fields = ["components", "members"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Conversation]:
        """Restrict the queryset to only include conversations that are not IncidentChannels. Incident channels are managed in the IncidentChannelAdmin."""
        qs = super().get_queryset(request)

        return Conversation.objects.not_incident_channel(qs)

    @admin.action(description="Update conversations members and info from Slack")
    def update_members(
        self, request: HttpRequest, queryset: QuerySet[Conversation]
    ) -> None:
        failed_updates = fetch_conversations_members_from_slack(queryset=queryset)
        success_len = len(queryset) - len(failed_updates)
        failed_len = len(failed_updates)
        if success_len > 0:
            self.message_user(
                request,
                ngettext(
                    "Updated members and info for %d Slack conversations.",
                    "Updated members and info for %d Slack conversations.",
                    success_len,
                )
                % success_len,
                SUCCESS,
            )
        if failed_len > 0:
            self.message_user(
                request=request,
                message=mark_safe(  # noqa: S308
                    ngettext(
                        "Failed to update members and info for %d Slack conversations",
                        "Failed to update members and info for %d Slack conversations",
                        failed_len,
                    )
                    % failed_len
                    + ": <br/>"
                    + format_html_join(
                        "<br/>",
                        "<a href={}> {}</a>",
                        (
                            (
                                reverse(
                                    "admin:slack_conversation_change", args=(g.id,)
                                ),
                                g,
                            )
                            for g in failed_updates
                        ),
                    )
                ),
                level=ERROR,
            )

    actions = [update_members]


@admin.register(IncidentChannel)
class IncidentChannelAdmin(ConversationAdmin):
    model: type[IncidentChannel] = IncidentChannel
    list_display = [
        "incident_id",
        "name",
        "channel_id",
        "_type",
        "_status",
        "is_shared",
    ]
    list_display_links = [
        "name",
        "channel_id",
    ]
    list_max_show_all = 500
    search_fields = ["channel_id", "name", "incident__id"]
    exclude = ("components",)
    readonly_fields = ("members",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[IncidentChannel]:
        qs = self.model._default_manager.get_queryset()  # noqa: SLF001

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin[Message]):
    model = Message
    list_display = ["ts", "conversation", "user", "ff_type", "text"]
    list_display_links = ["ts", "text"]
    list_max_show_all = 500
    search_fields = [
        "text",
        "conversation__channel_id",
        "conversation__name",
        "user__slack_id",
        "user__username",
        "ff_type",
    ]
    ordering = ["-ts"]
    list_filter = ["ff_type"]


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin[UserGroup]):
    model = UserGroup

    autocomplete_fields = ["components", "members"]
    search_fields = ["name", "handle", "usergroup_id"]

    def save_model(
        self,
        request: HttpRequest,
        obj: UserGroup,
        form: ModelForm[UserGroup],
        change: bool,  # noqa: FBT001
    ) -> None:
        # If added, check that we have all properties, or fetch them from Slack.
        if not change and not (
            obj.usergroup_id and obj.handle and obj.description and obj.name
        ):
            fetch_obj = None
            if obj.usergroup_id:
                fetch_obj = UserGroup.objects.fetch_usergroup(
                    group_slack_id=obj.usergroup_id
                )
            elif obj.handle:
                if obj.handle.startswith("@"):
                    obj.handle = obj.handle[1:]
                obj.handle.strip()
                fetch_obj = UserGroup.objects.fetch_usergroup(group_handle=obj.handle)
            if fetch_obj:
                obj.description = fetch_obj.description
                obj.name = fetch_obj.name
                obj.handle = fetch_obj.handle
                obj.is_external = fetch_obj.is_external
                obj.usergroup_id = fetch_obj.usergroup_id
                messages.add_message(
                    request,
                    messages.INFO,
                    "The usergroup has been updated with the information from Slack. Group members have not been linked, use the admin actions to fetch them.",
                )
            else:
                messages.add_message(
                    request,
                    messages.WARNING,
                    "Could not fetch your usergroup from Slack. A malformed usergroup has been saved to database. Please delete it, check your usergroup ID and try again.",
                )

        super().save_model(request, obj, form, change)

    @admin.action(description="Update usergroup members and info from Slack")
    def update_members(
        self, request: HttpRequest, queryset: QuerySet[UserGroup]
    ) -> None:
        failed_updates = update_usergroups_members_from_slack(queryset=queryset)
        success_len = len(queryset) - len(failed_updates)
        failed_len = len(failed_updates)
        if success_len > 0:
            self.message_user(
                request,
                ngettext(
                    "Updated members and info for %d Slack usergroup.",
                    "Updated members and info for %d Slack usergroups.",
                    success_len,
                )
                % success_len,
                SUCCESS,
            )
        if failed_len > 0:
            self.message_user(
                request=request,
                message=mark_safe(  # noqa: S308
                    ngettext(
                        "Failed to update members and info for %d Slack usergroup",
                        "Failed to update members and info for %d Slack usergroups",
                        failed_len,
                    )
                    % failed_len
                    + ": <br/>"
                    + format_html_join(
                        "<br/>",
                        "<a href={}> {}</a>",
                        (
                            (
                                reverse("admin:slack_usergroup_change", args=(g.id,)),
                                g,
                            )
                            for g in failed_updates
                        ),
                    )
                ),
                level=ERROR,
            )

    actions = [update_members]


class UserGroupInline(admin.StackedInline[UserGroup, Any]):
    model = UserGroup.components.through  # type: ignore[assignment]
    show_change_link = True
    extra = 0
    verbose_name = "Slack User Group"
    verbose_name_plural = "Slack User Groups"


class SlackUserInline(admin.StackedInline[SlackUser, Any]):
    model = SlackUser
    show_change_link = True
    extra = 1


class IncidentChannelInline(admin.StackedInline[IncidentChannel, Any]):
    model = IncidentChannel
    extra = 0
    verbose_name = "Slack Conversation"
    verbose_name_plural = "Slack Conversations"
    show_change_link = True

    @staticmethod
    def has_change_permission(*_: Any, **__: Any) -> bool:
        return False


class ConversationInline(admin.StackedInline[Conversation, Any]):
    model: type[Conversation] = Conversation.components.through  # type: ignore[assignment]
    extra = 0
    verbose_name = "Slack Conversation"
    show_change_link = True

    @staticmethod
    def has_change_permission(*_: Any, **__: Any) -> bool:
        return False


# Add inlines to incidents models
incidents.admin.user_inlines.append(SlackUserInline)
incidents.admin.component_inlines.append(UserGroupInline)
incidents.admin.component_inlines.append(ConversationInline)
incidents.admin.incident_inlines.append(IncidentChannelInline)

# Register Slack models
admin.site.register(Sos)


# Patch IncidentAdmin to add new actions
@action(description=_("Send a message to ask for key timestamps"))
def ask_key_timestamps(
    self: incidents.admin.IncidentAdmin,
    request: HttpRequest,
    queryset: QuerySet[Incident],
) -> None:
    """Will send a message to the Incident conversation (if it exists) to ask for key events.
    TODO Error handling.
    """
    # ruff: noqa: PLC0415
    from slack.views.modals.key_event_message import SlackMessageKeyEvents

    success: list[tuple[int, bool]] = []
    errors: list[tuple[int, bool, Exception | str]] = []
    for incident in queryset:
        if incident.conversation:
            try:
                incident.conversation.send_message_and_save(
                    SlackMessageKeyEvents(incident=incident)
                )
                success.append((incident.id, True))
            except SlackApiError as e:
                errors.append((incident.id, False, e))
        else:
            errors.append((incident.id, False, "No conversation"))

    if len(success) > 0:
        success_str = ", ".join(f"#{key[0]}" for key in success)
        self.message_user(
            request,
            ngettext(
                f"Sent message metrics for %d incident ({success_str}).",  # noqa: INT001
                f"Sent messages metrics for %d incidents ({success_str}).",
                len(success),
            )
            % len(success),
            constants.SUCCESS,
        )
    if len(errors) > 0:
        self.message_user(
            request,
            mark_safe(  # nosec # noqa: S308
                f"Error sending message: <br/>{'<br/>'.join(f'#{key[0]}: {key[2]}' for key in errors)}"
            ),
            constants.ERROR,
        )


incidents.admin.IncidentAdmin.actions.append(ask_key_timestamps)
