from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_CONFLUENCE = config("ENABLE_CONFLUENCE", cast=bool)
if ENABLE_CONFLUENCE:
    INSTALLED_APPS += ("firefighter.confluence",)

    CONFLUENCE_RUNBOOKS_FOLDER_ID: int = config(
        "CONFLUENCE_RUNBOOKS_FOLDER_ID", cast=int
    )
    CONFLUENCE_POSTMORTEM_TEMPLATE_PAGE_ID: int = config(
        "CONFLUENCE_POSTMORTEM_TEMPLATE_PAGE_ID", cast=int
    )
    CONFLUENCE_POSTMORTEM_FOLDER_ID: int = config(
        "CONFLUENCE_POSTMORTEM_FOLDER_ID", cast=int
    )
    CONFLUENCE_POSTMORTEM_SPACE: str = config("CONFLUENCE_POSTMORTEM_SPACE")

    CONFLUENCE_ON_CALL_PAGE_ID: int = config("CONFLUENCE_ON_CALL_PAGE_ID", cast=int)
    CONFLUENCE_USERNAME: str = config("CONFLUENCE_USERNAME")
    CONFLUENCE_API_KEY: str = config("CONFLUENCE_API_KEY")
    CONFLUENCE_URL: str = config("CONFLUENCE_URL")
    CONFLUENCE_MOCK_CREATE_POSTMORTEM: bool = config(
        "CONFLUENCE_MOCK_CREATE_POSTMORTEM", default=False, cast=bool
    )
