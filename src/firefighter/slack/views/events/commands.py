from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from slack_sdk.models.blocks.blocks import SectionBlock

from firefighter.firefighter import utils
from firefighter.slack.slack_app import SlackApp
from firefighter.slack.slack_templating import (
    slack_block_help_commands,
    slack_block_help_description,
    slack_block_help_tip,
)
from firefighter.slack.views.modals import (
    modal_close,
    modal_dowgrade_workflow,
    modal_edit,
    modal_open,
    modal_postmortem,
    modal_send_sos,
    modal_status,
    modal_trigger_oncall,
    modal_update,
)

if TYPE_CHECKING:
    from slack_bolt.context.ack.ack import Ack
    from slack_bolt.context.respond.respond import Respond
APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME
app = SlackApp()

logger = logging.getLogger(__name__)

SLACK_BUILTIN_COMMANDS = (
    "/archive",
    "/call",
    "/collapse",
    "/dm",
    "/expand",
    "/feed",
    "/invite",
    "/leave",
    "/msg",
    "/remind",
    "/remove",
    "/rename",
    "/search",
    "/shrug",
    "/status",
    "/topic",
)
"""List of all Slack built-in commands (https://slack.com/help/articles/201259356 checked August 2022)"""


def register_commands() -> None:
    """Register the command with its aliases.
    Commands are checked:
    - Fix commands that does not start with a slash, contain spaces, uppercase characters or are longer than 32 characters.
    - Ignore commands which names are built-in Slack commands.

    ⚠️ Don't forget to add the command and its aliases on your Slack App settings.
    """
    command_main: str = settings.SLACK_INCIDENT_COMMAND
    command_aliases: list[str] = settings.SLACK_INCIDENT_COMMAND_ALIASES

    commands = [command_main, *command_aliases]
    logger.debug(f"Registered commands: {commands}")
    for command in commands:
        if not command.startswith("/"):
            command = f"/{command}"  # noqa: PLW2901
            logger.warning(
                f"Command '{command}' does not start with a slash. We added one but please fix your configuration."
            )
        if " " in command:
            command = command.replace(" ", "")  # noqa: PLW2901
            logger.warning(
                f"Command '{command}' contained spaces. We removed them but please fix your configuration."
            )
        if len(command) > 32:
            command = command[:32]  # noqa: PLW2901
            logger.warning(
                f"Command '{command}' was longer than 32 characters. We truncated it but please fix your configuration."
            )
        if any(char.isupper() for char in command):
            command = command.lower()  # noqa: PLW2901
            logger.warning(
                f"Command '{command}' contained uppercase characters. We lower-cased them but please fix your configuration."
            )
        if command in SLACK_BUILTIN_COMMANDS:
            logger.warning(
                f"Command '{command}' is a built-in command, skipping registration. This command will not work."
            )
            continue
        app.command(command)(manage_incident)


def manage_incident(ack: Ack, respond: Respond, body: dict[str, Any]) -> None:
    logger.debug(body)
    command: str = utils.get_in(body, ["text"])

    if command is not None:
        command = command.lower().strip()

    if command == "open":
        modal_open.open_modal_aio(ack, body)
    elif command == "update":
        modal_update.open_modal_aio(ack, body)
    elif command == "edit":
        modal_edit.open_modal_aio(ack, body)
    elif command == "close":
        modal_close.open_modal_aio(ack=ack, body=body)
    elif command == "status":
        modal_status.open_modal_aio(ack=ack, body=body)
    elif command in {"oncall", "on-call"}:
        modal_trigger_oncall.open_modal_aio(ack=ack, body=body)
    elif command in {"postmortem", "post-mortem", "post mortem", "pm"}:
        modal_postmortem.open_modal_aio(ack=ack, body=body)
    elif command in {"sos", "sre", "sos-sre", "sos sre"}:
        modal_send_sos.open_modal_aio(ack=ack, body=body)
    elif command in {"downgrade", "convert"}:
        modal_dowgrade_workflow.open_modal_aio(ack=ack, body=body)
    elif command == "" or command is None:
        ack()
        send_help_message(respond=respond)
    else:
        ack()
        respond(text=f":x: Unknown command `{command}`!")
        send_help_message(respond=respond)


def send_help_message(respond: Respond) -> None:
    respond(
        text=f"{APP_DISPLAY_NAME} help",
        blocks=[
            SectionBlock(text=f"*{APP_DISPLAY_NAME} Commands Help*"),
            slack_block_help_description(),
            slack_block_help_commands(),
            slack_block_help_tip(),
        ],
    )


register_commands()
