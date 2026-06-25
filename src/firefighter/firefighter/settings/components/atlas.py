from __future__ import annotations

from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from firefighter.firefighter.settings.components.common import INSTALLED_APPS
from firefighter.firefighter.settings.settings_utils import config

ENABLE_ATLAS: bool = config("ENABLE_ATLAS", cast=bool, default=False)
"""Enable the Atlas Bot integration (automated incident analysis for P1/P2/P3)."""

if ENABLE_ATLAS:
    INSTALLED_APPS.append("firefighter.atlas")

    ATLAS_URL: str = config("ATLAS_URL")
    """Full URL of the Atlas Bot analyze endpoint (e.g. ``https://publicapi.company.com/platform-ops/incident/analyze``)."""

    _parsed = urlparse(ATLAS_URL)
    if _parsed.scheme != "https" or not _parsed.netloc:
        msg = f"ATLAS_URL must be an https URL, got: {ATLAS_URL!r}"
        raise ImproperlyConfigured(msg)

    ATLAS_SHARED_SECRET: str = config("ATLAS_SHARED_SECRET", default="")
    """Shared secret used to sign outgoing requests with HMAC-SHA256.
    Must match ``ATLAS_TRIGGER_SECRET`` configured in Atlas.
    When empty the Celery task logs a warning and skips the call."""
