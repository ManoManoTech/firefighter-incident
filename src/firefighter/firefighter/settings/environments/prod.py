"""This file contains all the settings used in production environments.

This file is required and if `ENV=dev` these values are not used.
"""

from __future__ import annotations

from pathlib import Path

from firefighter.firefighter.settings.settings_utils import config

# Production flags:
# https://docs.djangoproject.com/en/4.2/howto/deployment/

DEBUG = config("DEBUG", default=False, cast=bool)

# Staticfiles
# https://docs.djangoproject.com/en/4.2/ref/contrib/staticfiles/

# This is a hack to allow a special flag to be used with `--dry-run`
# to test things locally.
_COLLECTSTATIC_DRYRUN = config(
    "DJANGO_COLLECTSTATIC_DRYRUN",
    cast=bool,
    default=False,
)
# Adding STATIC_ROOT to collect static files via 'collectstatic':
STATIC_ROOT = Path(
    ".static"
    if _COLLECTSTATIC_DRYRUN
    else config("STATIC_ROOT", default="/var/app/django/.static")
)

STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}


# Media files
# https://docs.djangoproject.com/en/4.2/topics/files/

MEDIA_ROOT = "/var/app/django/media"


# Security
# https://docs.djangoproject.com/en/4.2/topics/security/

SECURE_HSTS_SECONDS = 31536000  # the same as Caddy has
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_REDIRECT_EXEMPT = [
    # This is required for healthcheck to work:
    r"^api/v2/firefighter/monitoring/healthcheck$",
]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
