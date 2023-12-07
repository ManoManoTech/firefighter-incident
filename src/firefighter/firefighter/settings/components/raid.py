from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_RAID: bool = config("ENABLE_RAID", cast=bool, default=False)

if ENABLE_RAID:
    INSTALLED_APPS += ("firefighter.raid",)

    # Default Jira user ID to use for creating issues
    RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = config("RAID_DEFAULT_JIRA_QRAFT_USER_ID")

    # The Jira project key to use for creating issues, e.g. "INC"
    RAID_JIRA_PROJECT_KEY: str = config("RAID_JIRA_PROJECT_KEY")

    # Link to the board with issues to qualify
    RAID_QUALIFIER_URL: str = config("RAID_QUALIFIER_URL")

    # Mapping of domain to default Jira user ID
    RAID_JIRA_USER_IDS: dict[str, str] = {}
