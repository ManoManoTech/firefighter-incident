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

    from firefighter.incidents.models.incident import Incident
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


def md_quote_filter[T](val: str | T) -> str | T:
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


COMMANDER_ACTION_OPENING = (
    "you are the *Incident Commander*: you lead the process through to closure. You don't have to"
    " do all the work, but you are in charge of guiding the team — including making sure the"
    " post-mortem is carried out before the incident is closed."
)
"""Ownership sentence for the start of the incident, when roles are first announced."""

COMMANDER_ACTION_POSTMORTEM = (
    "as *Incident Commander*, it's on you to organize the post-mortem and see it through before"
    " closure. You don't have to write it all yourself — you own getting it done."
)
"""Ownership sentence for incidents that require a post-mortem before closure."""

COMMANDER_ACTION_CLOSURE = (
    "as *Incident Commander*, it's on you to get the key events submitted and to close this"
    " incident."
)
"""Ownership sentence for incidents that close without a post-mortem."""

COMMANDER_UNASSIGNED = (
    "No *Incident Commander* is assigned on this incident — someone needs to take the role to"
    " drive it through to closure."
)
"""Shown instead of a mention when nobody holds command."""

ROLE_REASSIGNMENT_HINT = (
    ":bulb: _Not the right person for a role? Talk it over in this channel so a more suitable"
    " responder can take it over, with their agreement, then reassign the role._"
)
"""Invitation to hand a role over, with the consent of whoever picks it up."""


def _roles_guide_suffix() -> str:
    roles_guide_url = settings.SLACK_ROLES_GUIDE_URL
    if not roles_guide_url:
        return ""
    return f" <{roles_guide_url}|Your role in detail>."


def commander_ownership_block(incident: Incident, action: str) -> SectionBlock:
    """Remind whoever holds command that they own driving the process, or that nobody does.

    Args:
        incident: the incident to read the commander from. Callers looping over incidents should
            `prefetch_related("roles_set__role_type", "roles_set__user__slack_user")`.
        action: the ownership sentence to use, e.g. [COMMANDER_ACTION_POSTMORTEM][firefighter.slack.slack_templating.COMMANDER_ACTION_POSTMORTEM].
    """
    commander = incident.commander
    if commander is None or commander.user is None:
        return SectionBlock(
            text=MarkdownTextObject(
                text=f":rotating_light: {COMMANDER_UNASSIGNED}{_roles_guide_suffix()}"
            )
        )
    return SectionBlock(
        text=MarkdownTextObject(
            text=f"{commander.role_type.emoji} {user_slack_handle_or_name(commander.user)} {action}{_roles_guide_suffix()}"
        )
    )


def slack_block_role_reassignment_hint() -> ContextBlock:
    return ContextBlock(elements=[MarkdownTextObject(text=ROLE_REASSIGNMENT_HINT)])
