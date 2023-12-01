from __future__ import annotations

from decouple import Csv

from firefighter.firefighter.settings.settings_utils import config

# can't disable Slack.. yet?
ENABLE_SLACK: bool = True

SLACK_BOT_TOKEN: str = config("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET: str = config("SLACK_SIGNING_SECRET")
SLACK_SEVERITY_HELP_GUIDE_URL: str = config("SLACK_SEVERITY_HELP_GUIDE_URL")
SLACK_INCIDENT_HELP_GUIDE_URL: str = config("SLACK_INCIDENT_HELP_GUIDE_URL")
SLACK_CURRENT_ONCALL_URL: str = config("SLACK_CURRENT_ONCALL_URL")
SLACK_POSTMORTEM_HELP_URL: str = config("SLACK_POSTMORTEM_HELP_URL")
SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL: str = config(
    "SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL"
)
SLACK_EMERGENCY_USERGROUP_ID: str = config("SLACK_EMERGENCY_USERGROUP_ID")
SLACK_INCIDENT_COMMAND: str = config("SLACK_INCIDENT_COMMAND")
SLACK_INCIDENT_COMMAND_ALIASES: list[str] = config(
    "SLACK_INCIDENT_COMMAND_ALIASES", cast=Csv(), default=""
)
SLACK_APP_EMOJI: str = config("SLACK_APP_EMOJI", default=":fire_extinguisher:")
"""Emoji to represent the app in Slack surfaces. Can be an actual emoji, or a string for a custom emoji present in your Workspace, like ":incident_logo:"."""


FF_SLACK_SKIP_CHECKS: bool = config("FF_SLACK_SKIP_CHECKS", cast=bool, default=True)
"""Skip Slack checks. Only use for testing or demo."""
