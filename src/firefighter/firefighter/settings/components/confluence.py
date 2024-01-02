from __future__ import annotations

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_CONFLUENCE = config("ENABLE_CONFLUENCE", cast=bool, default=False)
"Enable the Confluence app."

if ENABLE_CONFLUENCE:
    INSTALLED_APPS += ("firefighter.confluence",)

    CONFLUENCE_RUNBOOKS_FOLDER_ID: int = config(
        "CONFLUENCE_RUNBOOKS_FOLDER_ID", cast=int
    )
    "The Confluence page ID where runbooks are stored."

    CONFLUENCE_POSTMORTEM_TEMPLATE_PAGE_ID: int = config(
        "CONFLUENCE_POSTMORTEM_TEMPLATE_PAGE_ID", cast=int
    )
    "The Confluence page ID of the template to use for postmortems."

    CONFLUENCE_POSTMORTEM_FOLDER_ID: int = config(
        "CONFLUENCE_POSTMORTEM_FOLDER_ID", cast=int
    )
    "The Confluence page ID  where to create and nest postmortems."

    CONFLUENCE_POSTMORTEM_SPACE: str = config("CONFLUENCE_POSTMORTEM_SPACE")
    "XXX To rename CONFLUENCE_DEFAULT_SPACE. The Confluence space where to create pages by default, mainly for postmortems."

    CONFLUENCE_ON_CALL_PAGE_ID: int | None = config(
        "CONFLUENCE_ON_CALL_PAGE_ID", cast=int, default=None
    )
    "The Confluence page ID where to export the current on-call schedule. If not set, export tasks will be skipped."

    CONFLUENCE_USERNAME: str = config("CONFLUENCE_USERNAME")
    "The Confluence username to use."
    CONFLUENCE_API_KEY: str = config("CONFLUENCE_API_KEY")
    "The Confluence API key to use."
    CONFLUENCE_URL: str = config("CONFLUENCE_URL")
    "The Confluence URL to use. If no protocol is defined, https will be used."
    CONFLUENCE_MOCK_CREATE_POSTMORTEM: bool = config(
        "CONFLUENCE_MOCK_CREATE_POSTMORTEM", default=False, cast=bool
    )
