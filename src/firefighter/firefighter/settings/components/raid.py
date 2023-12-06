from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_RAID: bool = config("ENABLE_RAID", cast=bool, default=False)

if ENABLE_RAID:
    INSTALLED_APPS += ("firefighter.raid",)
    RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = config("RAID_DEFAULT_JIRA_QRAFT_USER_ID")
    RAID_DEFAULT_JIRA_ARMATIS_USER_ID: str = config("RAID_DEFAULT_JIRA_ARMATIS_USER_ID")
    RAID_DEFAULT_JIRA_NEXUS_USER_ID: str = config("RAID_DEFAULT_JIRA_NEXUS_USER_ID")
    RAID_DEFAULT_JIRA_ADM_USER_ID: str = config("RAID_DEFAULT_JIRA_ADM_USER_ID")
    RAID_JIRA_API_VERSION: str = config("RAID_JIRA_API_VERSION")
    RAID_JIRA_PROJECT_KEY: str = config("RAID_JIRA_PROJECT_KEY")
    RAID_BASE_URL_API: str = config("RAID_BASE_URL_API")
    RAID_QUALIFIER_URL: str = config("RAID_QUALIFIER_URL")

    # XXX OSS: Move to mm_ff_settings
    RAID_JIRA_USER_IDS: dict[str, str] = {
***REMOVED***
***REMOVED***
***REMOVED***
***REMOVED***
***REMOVED***
***REMOVED***
    }
