from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_JIRA: bool = config("ENABLE_JIRA", cast=bool, default=False)
"Enable the Jira app."

if ENABLE_JIRA:
    INSTALLED_APPS += ("firefighter.jira_app",)

    RAID_JIRA_API_USER: str = config("RAID_JIRA_API_USER")
    """The Jira API user to use."""
    RAID_JIRA_API_PASSWORD: str = config("RAID_JIRA_API_PASSWORD")
    """The Jira API password to use."""
    RAID_JIRA_API_URL: str = config("RAID_JIRA_API_URL")
    """The Jira API URL to use. If no protocol is defined, https will be used."""

    if not RAID_JIRA_API_URL.startswith("http"):
        RAID_JIRA_API_URL = f"https://{RAID_JIRA_API_URL}"
    RAID_JIRA_API_URL = RAID_JIRA_API_URL.rstrip("/")

    # Jira Post-mortem Configuration
    ENABLE_JIRA_POSTMORTEM: bool = config(
        "ENABLE_JIRA_POSTMORTEM", cast=bool, default=False
    )
    "Enable Jira post-mortem creation (in addition to or instead of Confluence)."

    if ENABLE_JIRA_POSTMORTEM:
        JIRA_POSTMORTEM_PROJECT_KEY: str = config(
            "JIRA_POSTMORTEM_PROJECT_KEY", default="INCIDENT"
        )
        "Jira project key for post-mortems."

        JIRA_POSTMORTEM_ISSUE_TYPE: str = config(
            "JIRA_POSTMORTEM_ISSUE_TYPE", default="Post-mortem"
        )
        "Jira issue type for post-mortems."

        # Jira Custom Field IDs
        JIRA_POSTMORTEM_FIELDS: dict[str, str] = {
            "incident_summary": config(
                "JIRA_FIELD_INCIDENT_SUMMARY", default="customfield_12699"
            ),
            "timeline": config("JIRA_FIELD_TIMELINE", default="customfield_12700"),
            "root_causes": config("JIRA_FIELD_ROOT_CAUSES", default="customfield_12701"),
            "impact": config("JIRA_FIELD_IMPACT", default="customfield_12702"),
            "mitigation_actions": config(
                "JIRA_FIELD_MITIGATION_ACTIONS", default="customfield_12703"
            ),
            "incident_category": config(
                "JIRA_FIELD_INCIDENT_CATEGORY", default="customfield_12369"
            ),
        }
