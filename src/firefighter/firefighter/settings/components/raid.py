from __future__ import annotations

from decouple import Csv

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_RAID: bool = config("ENABLE_RAID", cast=bool, default=False)
"Enable the Raid app. Jira app must be enabled and configured as well."

if ENABLE_RAID:
    INSTALLED_APPS += ("firefighter.raid",)

    RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = config("RAID_DEFAULT_JIRA_QRAFT_USER_ID")
    "The default Jira user ID to use for creating issues"

    RAID_JIRA_PROJECT_KEY: str = config("RAID_JIRA_PROJECT_KEY")
    "The Jira project key to use for creating issues, e.g. 'INC'"

    RAID_JIRA_USER_IDS: dict[str, str] = {}
    "Mapping of domain to default Jira user ID"

    RAID_TOOLBOX_URL: str = config("RAID_TOOLBOX_URL")
    "Toolbox URL"

    RAID_JIRA_INCIDENT_CATEGORY_FIELD: str = config("RAID_JIRA_INCIDENT_CATEGORY_FIELD", default="")
    "Jira custom field ID for incident category (e.g. 'customfield_12345')"

    RAID_WATCHER_EMAIL_EXCLUSIONS: list[str] = [
        email.strip().lower()
        for email in config(
            "RAID_WATCHER_EMAIL_EXCLUSIONS",
            default="",
            cast=Csv(),
        )
        if email.strip()
    ]
    "Comma-separated emails to skip when notifying Jira ticket watchers. Use it for service or bot accounts that have no usable Slack mapping (e.g. shared automation users)."
