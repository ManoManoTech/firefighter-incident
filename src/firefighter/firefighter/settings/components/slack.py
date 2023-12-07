from __future__ import annotations

import sys

from decouple import Csv

from firefighter.firefighter.settings.settings_utils import config

# can't disable Slack.. yet?
ENABLE_SLACK: bool = True

SLACK_BOT_TOKEN: str = config("SLACK_BOT_TOKEN")
"""The Slack bot token to use."""
SLACK_SIGNING_SECRET: str = config("SLACK_SIGNING_SECRET")
"""The Slack signing secret to use."""
SLACK_SEVERITY_HELP_GUIDE_URL: str = config("SLACK_SEVERITY_HELP_GUIDE_URL")
SLACK_INCIDENT_HELP_GUIDE_URL: str = config("SLACK_INCIDENT_HELP_GUIDE_URL")
SLACK_CURRENT_ONCALL_URL: str = config("SLACK_CURRENT_ONCALL_URL")
SLACK_POSTMORTEM_HELP_URL: str = config("SLACK_POSTMORTEM_HELP_URL")
SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL: str = config(
    "SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL"
)
SLACK_EMERGENCY_USERGROUP_ID: str = config("SLACK_EMERGENCY_USERGROUP_ID")
SLACK_INCIDENT_COMMAND: str = config("SLACK_INCIDENT_COMMAND")
"""The Slack slash command to use to create and manage incidents."""
SLACK_INCIDENT_COMMAND_ALIASES: list[str] = config(
    "SLACK_INCIDENT_COMMAND_ALIASES", cast=Csv(), default=""
)
"Comma-separated list of aliases for the incident command."
SLACK_APP_EMOJI: str = config("SLACK_APP_EMOJI", default=":fire_extinguisher:")
"""Emoji to represent the app in Slack surfaces. Can be an actual emoji, or a string for a custom emoji present in your Workspace, like ":incident_logo:"."""

_default_skip_check = "generate_manifest" in sys.argv
FF_SLACK_SKIP_CHECKS: bool = config(
    "FF_SLACK_SKIP_CHECKS", cast=bool, default=_default_skip_check
)
"""Skip Slack checks. Only use for testing or demo."""
