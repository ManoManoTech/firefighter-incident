"""Django settings for server project.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their config, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from decouple import Csv

from firefighter.firefighter.settings.settings_utils import _ENV, BASE_DIR, config
from firefighter.firefighter.sso import link_auth_user

if TYPE_CHECKING:
    from collections.abc import Callable

SECRET_KEY: str = config("SECRET_KEY")
ENV = _ENV

# Application definition:
INSTALLED_APPS = [
    # Your apps go here:
    "firefighter.firefighter",
    "firefighter.incidents",
    "firefighter.slack",
    # Default django apps
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "django.forms",
    # django-admin
    "django.contrib.admin",
    "django.contrib.admindocs",
    # API
    "firefighter.api",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "drf_standardized_errors",
    # Other deps
    "widget_tweaks",
    "django_components",
    "django_htmx",
    "django_filters",
    "taggit",
    "django_tables2",
    "import_export",
    # SSO Auth
    "oauth2_authcodeflow",
    # Celery integration
    "django_celery_beat",
    # Menu generation from class
    "simple_menu",
]

MIDDLEWARE: tuple[str, ...] = (
    "django.middleware.security.SecurityMiddleware",
    # Whitenoise (serves assets) must come first, but after django.middleware.security.SecurityMiddleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Django:
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    # XXX We could make a single Middleware to replace AuthenticationMiddleware and LoginRequiredMiddleware
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "oauth2_authcodeflow.middleware.LoginRequiredMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "firefighter.firefighter.middleware.HeaderUser",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

ROOT_URLCONF = "firefighter.firefighter.urls"

WSGI_APPLICATION = "firefighter.firefighter.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

db_schema = config("POSTGRES_SCHEMA", default="")
db_options = {"options": "-c statement_timeout=30000"}
if db_schema:
    db_options["options"] += f" -c search_path={db_schema}"

DATABASES: dict[str, dict[str, Any]] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB"),
        "USER": config("POSTGRES_USER"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST"),
        "PORT": config("POSTGRES_PORT"),
        "OPTIONS": db_options,
    }
}

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en"

USE_I18N = False
USE_TZ = True
TIME_ZONE: str = config("TIME_ZONE", default="UTC")

# Localization
FORMAT_MODULE_PATH = ["firefighter.formats"]

# Default date filters
# Set in firefighter.formats as well
SHORT_DATE_FORMAT = "Y/m/d"
SHORT_DATETIME_FORMAT = "Y/m/d H:i"


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / ".static"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATICFILES_DIRS = [
    BASE_DIR / "components",
]
# Templates
# https://docs.djangoproject.com/en/4.2/ref/templates/api


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            Path(BASE_DIR.joinpath("templates")),
            Path(BASE_DIR.joinpath("components")),
        ],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "firefighter.firefighter.utils.get_global_context",
            ],
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                        "django_components.template_loader.Loader",
                    ],
                )
            ],
            "builtins": [
                "django_components.templatetags.component_tags",
            ],
        },
    },
]
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"


# Django authentication system
# https://docs.djangoproject.com/en/4.2/topics/auth/

AUTHENTICATION_BACKENDS = (
    "oauth2_authcodeflow.auth.AuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
)


# Security
# https://docs.djangoproject.com/en/4.2/topics/security/

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

_PASS = "django.contrib.auth.password_validation"  # noqa: S105 # nosec
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"{_PASS}.UserAttributeSimilarityValidator"},
    {"NAME": f"{_PASS}.MinimumLengthValidator"},
    {"NAME": f"{_PASS}.CommonPasswordValidator"},
    {"NAME": f"{_PASS}.NumericPasswordValidator"},
]

ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS: list[str] = config(
    "CSRF_TRUSTED_ORIGINS", default="https://*", cast=Csv()
)


SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Password hashing
# https://docs.djangoproject.com/en/4.2/topics/auth/passwords/#auth-password-storage
# Argon2 + defaults
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Can be removed when we upgrade to Django 5.0, which makes this the default
FORM_RENDERER = "django.forms.renderers.DjangoDivFormRenderer"

# Debug Flags
DEBUG_TOOLBAR = config("DEBUG_TOOLBAR", default=False, cast=bool)

USE_X_FORWARDED_HOST = True


#  Auth and SSO config
def get_django_username(x: dict[str, str]) -> str | None:
    username = x.get("preferred_username")
    if username is not None and "@" in username:
        return username.split("@")[0]
    return username


AUTH_USER_MODEL = "incidents.User"
OIDC_TIMEOUT: int = config("OIDC_TIMEOUT", cast=int, default=15)
OIDC_OP_DISCOVERY_DOCUMENT_URL = config("OIDC_OP_DISCOVERY_DOCUMENT_URL")
OIDC_RP_CLIENT_ID = config("OIDC_RP_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = config("OIDC_RP_CLIENT_SECRET")
OIDC_MIDDLEWARE_NO_AUTH_URL_PATTERNS = [
    "^/admin/",
    "^/__reload__/events/",
    "^/api/",
    "^/err/",
    "^/robots.txt$",
]

# noinspection PyPep8
OIDC_DJANGO_USERNAME_FUNC = get_django_username
OIDC_CREATE_USER = True
OIDC_EXTEND_USER = link_auth_user
OIDC_UNUSABLE_PASSWORD = config("OIDC_UNUSABLE_PASSWORD", default=False, cast=bool)
OIDC_RP_USE_PKCE = config("OIDC_RP_USE_PKCE", default=False, cast=bool)
# Default login redirect
LOGIN_URL = "/admin/login/"

# Plausible analytics configuration

PLAUSIBLE_SCRIPT_URL: str = config("PLAUSIBLE_SCRIPT_URL", "")
PLAUSIBLE_DOMAIN: str = config("PLAUSIBLE_DOMAIN", "")


# Components
COMPONENTS = {
    "autodiscover": False,
    "context_behavior": "django",  # Like before django-components 0.67
    "libraries": [
        "firefighter.components.avatar.avatar",
        "firefighter.components.card.card",
        "firefighter.components.export_button.export_button",
        "firefighter.components.form.form",
        "firefighter.components.form_field.form_field",
        "firefighter.components.modal.modal",
        "firefighter.components.messages.messages",
    ],
}


# FF specific options
FF_ROLE_REMINDER_MIN_DAYS_INTERVAL = config(
    "FF_ROLE_REMINDER_MIN_DAYS_INTERVAL", default=90, cast=int
)
"Number of days between role explanation/reminders, for each role. -1 disable the messages, and 0 will send the message everytime."

FF_HTTP_CLIENT_ADDITIONAL_HEADERS: dict[str, Any] | None = None
"Additional headers to send with every HTTP request made using our HttpClient. Useful for global auth, or adding a specific User-Agent."

FF_USER_ID_HEADER: str = "FF-User-Id"
"Header name to add to every HTTP request made using our HttpClient. Useful for logging."

FF_OVERRIDE_MENUS_CREATION: Callable[[], None] | None = None
"Override the default menus creation. Useful for custom menus."

FF_DEBUG_ERROR_PAGES: bool = config("FF_DEBUG_ERROR_PAGES", default=False, cast=bool)
"Add routes to display error pages. Useful for debugging."

FF_SKIP_SECRET_KEY_CHECK: bool = config(
    "FF_SKIP_SECRET_KEY_CHECK", default=False, cast=bool
)
"Skip the SECRET_KEY check. Make sure to set a strong SECRET_KEY in production."

FF_EXPOSE_API_DOCS: bool = config("FF_EXPOSE_API_DOCS", default=False, cast=bool)
"Expose the API documentation. Useful for debugging. Can be a security issue."
