from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from django.conf import settings
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.blocks import (
    Block,
    DividerBlock,
    SectionBlock,
)

from firefighter.slack.messages.base import SlackMessageSurface
from firefighter.slack.slack_templating import user_slack_handle_or_name

if TYPE_CHECKING:
    from collections.abc import Iterable

    from firefighter.incidents.models.user import User
    from firefighter.raid.models import JiraTicket, JiraUser, QualifierRotation

RAID_QUALIFIER_URL: str = settings.RAID_QUALIFIER_URL
RAID_JIRA_API_URL: str = settings.RAID_JIRA_API_URL


class SlackMessageRaidCreatedIssue(SlackMessageSurface):
    id = "raid_created_issue"

    def __init__(self, ticket: JiraTicket, reporter_user: User | None = None) -> None:
        self.ticket = ticket
        self.reporter_user = reporter_user if reporter_user else ticket.reporter.user
        super().__init__()

    def get_text(self) -> str:
        return f"New {self.ticket.issue_type}: {self.ticket.key} '{self.ticket.summary}' was created."

    def get_blocks(self) -> list[Block]:
        blocks: list[Block] = [
            SectionBlock(
                text=f"New { self.ticket.issue_type}: *{self.ticket.key}* _ {self.ticket.summary} _ was created."
            ),
            # XXX Add issue type emoji from RAID
            DividerBlock(),
            SectionBlock(
                fields=[
                    MarkdownTextObject(text=f":tag: *Title:*\n{self.ticket.summary}"),
                    MarkdownTextObject(
                        text=textwrap.shorten(
                            f":spiral_note_pad: *Description:*\n{self.ticket.description}",
                            width=1997,
                            placeholder="...",
                        )
                    ),
                    MarkdownTextObject(
                        text=f":happydoge: *Reporter:*\n{user_slack_handle_or_name(self.reporter_user)}"
                    ),
                    MarkdownTextObject(text=f":jira_new: *Jira:*\n{self.ticket.url}"),
                    MarkdownTextObject(
                        text=f":warning: *Business impact*: {self.ticket.business_impact if self.ticket.business_impact else 'N/A'}"
                    ),
                ]
            ),
        ]
        return blocks


class SlackMessageRaidModifiedIssue(SlackMessageSurface):
    id = "raid_modify_issue"

    def __init__(
        self,
        jira_ticket_key: str,
        jira_author_name: str,
        jira_field_modified: str,
        jira_field_from: str,
        jira_field_to: str,
    ) -> None:
        self.jira_ticket_key = jira_ticket_key
        self.jira_author_name = jira_author_name
        self.jira_field_modified = jira_field_modified
        self.jira_field_from = jira_field_from
        self.jira_field_to = jira_field_to
        super().__init__()

    def get_text(self) -> str:
        return f"Modified Jira ticket {self.jira_ticket_key}"

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(
                text=f":jira_new: Jira ticket *{self.jira_ticket_key}* was *modified* :hammer:"
            ),
            DividerBlock(),
            SectionBlock(
                fields=[
                    MarkdownTextObject(
                        text=f":face_with_monocle: *Author:*\n{self.jira_author_name}"
                    ),
                    MarkdownTextObject(
                        text=f":tag: *Field:*\n{self.jira_field_modified}"
                    ),
                    MarkdownTextObject(text=f":x: *From:*\n{self.jira_field_from}"),
                    MarkdownTextObject(
                        text=f":light_check_mark: *To:*\n{self.jira_field_to}"
                    ),
                    MarkdownTextObject(
                        text=f":jira_new: *URL:*\n{RAID_JIRA_API_URL}/browse/{self.jira_ticket_key}"
                    ),
                ]
            ),
        ]


class SlackMessageRaidComment(SlackMessageSurface):
    id = "raid_comment"

    def __init__(
        self,
        jira_ticket_key: str,
        author_jira_name: str,
        comment: str,
        webhook_event: str,
    ) -> None:
        self.jira_ticket_key = jira_ticket_key
        self.author_jira_name = author_jira_name
        self.comment = comment
        self.webhook_event = webhook_event
        match self.webhook_event:
            case "comment_created":
                self.comment_event_text = ":green_book: New comment added"
            case "comment_updated":
                self.comment_event_text = ":blue_book: Updated comment"
            case "comment_deleted":
                self.comment_event_text = ":closed_book: Deleted comment"
        super().__init__()

    def get_text(self) -> str:
        return f"{self.comment_event_text} on {self.jira_ticket_key}"

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(
                text=f"{self.comment_event_text} on the Jira ticket *{self.jira_ticket_key}*"
            ),
            DividerBlock(),
            SectionBlock(
                fields=[
                    MarkdownTextObject(
                        text=f":face_with_monocle: *Author:*\n{self.author_jira_name}"
                    ),
                    MarkdownTextObject(text=f":pencil2: *Comment:*\n{self.comment}"),
                    MarkdownTextObject(
                        text=f":jira_new: *Jira:*\n{RAID_JIRA_API_URL}/browse/{self.jira_ticket_key}"
                    ),
                ]
            ),
        ]


class SlackMessageRaidDailyQualifierPublic(SlackMessageSurface):
    id = "raid_daily_qualifier_public"

    def __init__(self, qualifier: JiraUser) -> None:
        self.qualifier = qualifier
        super().__init__()

    def get_text(self) -> str:
        return f"Daily qualifier {user_slack_handle_or_name(self.qualifier.user)}"

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(text="*Daily qualifier*"),
            DividerBlock(),
            SectionBlock(
                fields=[
                    MarkdownTextObject(
                        text=f"Hello! :wave: \nToday the Qualifier is {user_slack_handle_or_name(self.qualifier.user)}"
                    ),
                ]
            ),
        ]


class SlackMessageRaidDailyQualifierPrivate(SlackMessageSurface):
    id = "raid_daily_qualifier_private"

    def get_text(self) -> str:
        return "Daily qualifier"

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(text="*Daily qualifier*"),
            DividerBlock(),
            SectionBlock(
                fields=[
                    MarkdownTextObject(
                        text="Don't forget, you're the Qualifier today! :muscle:\n"
                    ),
                    MarkdownTextObject(
                        text=f"\nIssues to qualify can be tracked here: {RAID_QUALIFIER_URL}\n"
                    ),
                    MarkdownTextObject(text="Have a good day! :lovecommunity:"),
                ]
            ),
        ]


class SlackMessageRaidWeeklyQualifiers(SlackMessageSurface):
    id = "raid_weekly_qualifiers_public"

    def __init__(self, qualifiers_rotation: Iterable[QualifierRotation]) -> None:
        # Obtain weekly qualifier rotation in a readable format
        self.rotation_text = ""
        for rotation in qualifiers_rotation:
            self.rotation_text = (
                self.rotation_text
                + f"{(rotation.day.strftime('%a %d/%m/%Y'))} --> {user_slack_handle_or_name(rotation.jira_user.user)}\n"
            )
        super().__init__()

    def get_text(self) -> str:
        return "Weekly qualifier rotation"

    def get_blocks(self) -> list[Block]:
        return [
            SectionBlock(
                text="Hello! :wave: \nHere you can find *next week qualifier rotation*:"
            ),
            DividerBlock(),
            SectionBlock(fields=[MarkdownTextObject(text=f"{self.rotation_text}")]),
            SectionBlock(
                fields=[
                    MarkdownTextObject(
                        text="\n:pray: Please find a *backup* in case you won't be available."
                    ),
                ]
            ),
        ]
