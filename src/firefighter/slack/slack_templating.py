from __future__ import annotations

import logging
from functools import cache
from textwrap import TextWrapper
from typing import TYPE_CHECKING, Any, TypeVar

from django.conf import settings
from django.utils.timezone import localtime
from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.blocks import ContextBlock, DividerBlock, SectionBlock

from firefighter.slack.models.conversation import Conversation

if TYPE_CHECKING:
    from datetime import datetime

    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)

COMMAND: str = settings.SLACK_INCIDENT_COMMAND
INCIDENT_DOC_URL: str | None = settings.SLACK_INCIDENT_HELP_GUIDE_URL


def shorten_long(text: str, width: int, **kwargs: Any) -> str:
    """Shorten text while keeping newlines and most formatting."""
    kwargs.setdefault("placeholder", " [...]")
    kwargs.setdefault("tabsize", 4)
    kwargs.setdefault("max_lines", 1)
    kwargs.setdefault("drop_whitespace", False)
    kwargs.setdefault("replace_whitespace", False)
    kwargs.setdefault("break_long_words", True)
    w = TextWrapper(
        width=width,
        **kwargs,
    )
    return w.fill(text)


T = TypeVar("T")


def md_quote_filter(val: str | T) -> str | T:
    """Add > on newlines for MD quotes."""
    if isinstance(val, str):
        return val.replace("\n", "\n> ")
    return val


@cache
def date_time(date: datetime | None) -> str:
    """Common format for datetime.

    Args:
        date (datetime | None): your datetime

    Returns:
        str: datetime in format `YYYY-MM-DD HH:MM`
    """
    return localtime(date).strftime("%Y-%m-%d %H:%M")


def user_slack_handle_or_name(user: User | None) -> str:
    """Returns the Slack handle of the user in Slack MD format (`<@SLACK_ID>`) or the user full name."""
    if user is None:
        return "∅"

    if hasattr(user, "slack_user") and user.slack_user:
        return f"<@{user.slack_user.slack_id}>"
    return user.full_name


@cache
def slack_block_footer() -> ContextBlock:
    support_channel = Conversation.objects.get_or_none(tag="dev_firefighter")
    support_text = (
        f" Support and feedback in <#{support_channel.channel_id}>"
        if support_channel
        else ""
    )
    return ContextBlock(
        elements=[
            MarkdownTextObject(
                text=f"{settings.SLACK_APP_EMOJI}  {settings.APP_DISPLAY_NAME} {settings.FF_VERSION}. {support_text}"
            )
        ]
    )


@cache
def slack_block_separator() -> DividerBlock:
    return DividerBlock()


@cache
def slack_block_help_commands() -> SectionBlock:
    return SectionBlock(
        text=f"- `{COMMAND} open`: open an incident to start investigation\n- `{COMMAND} update`: update incident roles or statuses\n- `{COMMAND} close`: close an incident and archive the channel\n- `{COMMAND} status`: get a recap of the incident from this channel\n- `{COMMAND} oncall`: select an on-call you want to call\n- `{COMMAND} postmortem`: create the postmortem if needed\n- `{COMMAND} sos`: ask for SRE help"
    )


@cache
def slack_block_help_description() -> SectionBlock:
    if INCIDENT_DOC_URL is None:
        return SectionBlock(
            text=f"{settings.APP_DISPLAY_NAME} is our tool for incident management."
        )
    return SectionBlock(
        text=f"{settings.APP_DISPLAY_NAME} is our tool for incident management, more about incidents is visible <{INCIDENT_DOC_URL}|here>."
    )


@cache
def slack_block_help_tip() -> SectionBlock:
    return SectionBlock(
        text="A good incident response process involves great communication with internal and external stakeholders!"
    )


def slack_block_quote(text: str, length: int = 2995) -> SectionBlock:
    return SectionBlock(text=f"> {shorten_long(md_quote_filter(text), length)}")
