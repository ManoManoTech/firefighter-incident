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

    RAID_JIRA_WEBHOOK_SECRET: str = config("RAID_JIRA_WEBHOOK_SECRET", default="")
    "Shared secret expected as `?secret=` on Jira webhook calls to `raid/jira_update` and `raid/jira_comment`. Empty disables the endpoints (fail-closed)."

    RAID_JIRA_REJECT_TRANSITION: str = config("RAID_JIRA_REJECT_TRANSITION", default="Reject")
    "Name of the Jira transition that rejects a ticket, applied when an incident is closed as Rejected."

    RAID_JIRA_REJECTED_RESOLUTION: str = config("RAID_JIRA_REJECTED_RESOLUTION", default="Rejected")
    "Jira resolution set by the reject transition. A ticket with it rejects its incident (Jira -> IMPACT)."

    RAID_JIRA_REJECT_REASON_FIELD: str = config("RAID_JIRA_REJECT_REASON_FIELD", default="customfield_10943")
    "Jira select field the reject transition requires (e.g. 'Reason'). Empty if the transition requires none."

    RAID_JIRA_REJECT_REASON_VALUES: dict[str, str] = {
        "duplicate": config("RAID_JIRA_REJECT_REASON_DUPLICATE", default="Duplicated"),
        "superseded": config("RAID_JIRA_REJECT_REASON_SUPERSEDED", default="Duplicated"),
        "false_positive": config("RAID_JIRA_REJECT_REASON_FALSE_POSITIVE", default="Expected behaviour"),
        "cancelled": config("RAID_JIRA_REJECT_REASON_CANCELLED", default="Expected behaviour"),
    }
    "Option of the reject reason field for each rejection closure reason. The exact reason always goes in the Jira comment."
