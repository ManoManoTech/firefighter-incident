"""This file contains all the settings that defines the development server.

SECURITY WARNING: don't run with debug turned on in production!
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from firefighter.firefighter.settings.components.common import (
    DATABASES,
    INSTALLED_APPS,
    MIDDLEWARE,
    PASSWORD_HASHERS,
    TEMPLATES,
)
from firefighter.firefighter.settings.settings_utils import config

if TYPE_CHECKING:
    from pathlib import Path

    from django.http import HttpRequest

# Setting the development status:
DEBUG = config("DEBUG", default=True, cast=bool)
DEBUG_SILK = config("DEBUG_SILK", default=False, cast=bool)

# Allow all hosts
ALLOWED_HOSTS = [
    "localhost",
    "0.0.0.0",  # nosec # noqa: S104
    "127.0.0.1",
    "[::1]",
    "*",
]  # noqa: S104 # nosec

# Set MD5 as the default password hashing (faster)
PASSWORD_HASHERS.insert(0, "django.contrib.auth.hashers.MD5PasswordHasher")

# Remove password validators
AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

# Installed apps for development only:

# Load django-extensions
GRAPH_MODELS = {
    "all_applications": True,
    "group_models": True,
}
INSTALLED_APPS.append("django_extensions")
INSTALLED_APPS.append("django_watchfiles")
INSTALLED_APPS.append("extra_checks")
INSTALLED_APPS.append("nplusone.ext.django")
INSTALLED_APPS.append("django_browser_reload")
# XXX Add checks on migrations in CI (`./manage.py lintmigrations`)
# Django-migration-linter is configured in pyproject.toml
INSTALLED_APPS.append("django_migration_linter")


# XXX(GabDug): Implement pytest tests with django-test-migrations
# XXX(GabDug): Enable django_test_migrations.contrib.django_checks.AutoNames app after squashing migrations
# Django-test-migrations aka DTM (configured here)
INSTALLED_APPS.append("django_test_migrations")
INSTALLED_APPS.append(
    "django_test_migrations.contrib.django_checks.DatabaseConfiguration"
)

DTM_IGNORED_MIGRATIONS = {
    ("django_celery_beat", "*"),
    ("oauth2_authcodeflow", "*"),
    ("taggit", "*"),
    ("authtoken", "*"),
}


# Add the debug toolbar
if config("DEBUG_TOOLBAR", default=False, cast=bool):
    INSTALLED_APPS.append("debug_toolbar")

if config("DEBUG_SILK", default=False, cast=bool):
    INSTALLED_APPS.append("silk")
    SILKY_PYTHON_PROFILER = True
    SILKY_META = True

# Static files:
# https://docs.djangoproject.com/en/4.2/ref/settings/#std:setting-STATICFILES_DIRS

STATICFILES_DIRS: list[Path] = []


# Django debug toolbar:
# https://django-debug-toolbar.readthedocs.io

MIDDLEWARE += (
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
    # https://github.com/bradmontgomery/django-querycount
    # Prints how many queries were executed, useful for the APIs.
    # 'querycount.middleware.QueryCountMiddleware',
)
if DEBUG_SILK:
    MIDDLEWARE = (*MIDDLEWARE, "silk.middleware.SilkyMiddleware")  # noqa: WPS440


def _custom_show_toolbar(request: HttpRequest) -> bool:
    """Only show the debug toolbar to users with the superuser flag."""
    return DEBUG and request.user.is_superuser


DEBUG_TOOLBAR_CONFIG = {
    "SHOW_TOOLBAR_CALLBACK": "firefighter.firefighter.settings.environments.dev._custom_show_toolbar",
}

# This will make debug toolbar to work with django-csp,
# since `ddt` loads some scripts from `ajax.googleapis.com`:
CSP_SCRIPT_SRC = ("'self'", "ajax.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:")
CSP_CONNECT_SRC = ("'self'",)


# nplusone - Detect costly lazy loading from Django ORM
# https://github.com/jmcarp/nplusone

# Should be the first in line:
MIDDLEWARE = ("nplusone.ext.django.NPlusOneMiddleware", *MIDDLEWARE)  # noqa: WPS440

# Logging N+1 requests:
NPLUSONE_RAISE = False
NPLUSONE_LOGGER = logging.getLogger("nplusone")
NPLUSONE_LOG_LEVEL = logging.WARNING
NPLUSONE_WHITELIST = [
    {"model": "admin.*"},
]


# django-extra-checks - More Django best practices
# https://github.com/kalekseev/django-extra-checks

EXTRA_CHECKS = {
    "checks": [
        # Forbid `unique_together`:
        "no-unique-together",
        # Require non empty `upload_to` argument:
        "field-file-upload-to",
        # Each model must be registered in admin:
        # "model-admin",
        # FileField/ImageField must have non-empty `upload_to` argument:
        "field-file-upload-to",
        # Text fields shouldn't use `null=True`:
        # "field-text-null",
        # Don't pass `null=False` to model fields (this is django default)
        "field-null",
        # ForeignKey fields must specify db_index explicitly if used in
        # other indexes:
        {"id": "field-foreign-key-db-index", "when": "indexes"},
        # If field nullable `(null=True)`,
        # then default=None argument is redundant and should be removed:
        "field-default-null",
        # Fields with choices must have companion CheckConstraint
        # to enforce choices on database level
        "field-choices-constraint",
        # DRF Specific
        # Each ModelSerializer.Meta must have all attributes specified in attrs
        "drf-model-serializer-extra-kwargs",
        # "field-related-name",
    ],
    "include_apps": [
        "firefighter.incidents",
        "firefighter.api",
        "firefighter.slack",
        "firefighter.confluence",
        "firefighter.pagerduty",
        "firefighter.firefighter",
    ],
}

# Disable persistent DB connections
# https://docs.djangoproject.com/en/4.2/ref/databases/#caveats
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Force Debug on Django templating system
TEMPLATES[0]["OPTIONS"] |= {"debug": True}  # type: ignore[operator]


FF_DEBUG_ERROR_PAGES = config("FF_DEBUG_ERROR_PAGES", default=True, cast=bool)


FF_EXPOSE_API_DOCS: bool = config("FF_EXPOSE_API_DOCS", default=True, cast=bool)


FF_DEBUG_NO_SSO_REDIRECT: bool = config(
    "FF_DEBUG_NO_SSO_REDIRECT", default=False, cast=bool
)

if FF_DEBUG_NO_SSO_REDIRECT:
    MIDDLWARE = tuple(
        middleware
        for middleware in MIDDLEWARE
        if middleware != "oauth2_authcodeflow.middleware.LoginRequiredMiddleware"
    )
    OIDC_MIDDLEWARE_LOGIN_REQUIRED_REDIRECT = False
