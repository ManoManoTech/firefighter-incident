from __future__ import annotations

from firefighter.firefighter.settings.settings_utils import (
    _ENV,
    APP_DISPLAY_NAME,
    BASE_URL,
    FF_VERSION,
)

# DRF - Django REST Framework settings
# https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "firefighter.api.authentication.BearerTokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # StrictDjangoModelPermissions is DjangoModelPermissions that also checks the model view permissions for GET requests.
    "DEFAULT_PERMISSION_CLASSES": [
        "firefighter.api.permissions.StrictDjangoModelPermissions"
    ],
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "firefighter.api.renderer.CSVRenderer",
        "firefighter.api.renderer.TSVRenderer",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_standardized_errors.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}


# DRF Spectacular
# https://drf-spectacular.readthedocs.io/en/latest/settings.html
SPECTACULAR_SETTINGS = {
    "TITLE": f"{APP_DISPLAY_NAME} API (FF {FF_VERSION})",
    "DESCRIPTION": f"""Get data, create incidents.\n

### Support and compatibility

Versioning of the API is independent of {APP_DISPLAY_NAME} versioning.

The API is still in development, and may change without notice.

The API currently does not provides versioning, but it may in the future.

### Auth

#### Authentication

For simplicity's sake, only the Token Bearer Auth security scheme is shown,
but Django Session Auth is also supported for authorized endpoints.

> Ask your administrator if you need a token.

#### Authorization

Authorization is done using Django's permissions system.

It currently may not be respected by the API, but it will be in the future.

### Formats

All endpoints support JSON. Read-only endpoints usually support CSV and TSV in addition to JSON.

#### Tabular formats

Tabular formats CSV and TSV support the `fields` query parameter to select which fields to return.

It is ignored for JSON.

#### Content negotiation

To request a specific format, you should use the `Accept` header.

There are also two alternatives, that are not recommended and will be deprecated in the future:
- Use the `format` query parameter
- Add the file extension to the URL

Mixing different ways to request a format may lead to unexpected results and errors.

### Pagination

Endpoints are not yet paginated, but it will be in the future.

### Errors

Errors format are standardized, and are documented in the OpenAPI schema.

Some errors are not documented in this schema, as they should not happen if you follow the spec:
- `405` Method Not Allowed: you should use the right method
- `406` Not Acceptable: you should use the right Accept header
- `415` Unsupported Media Type: you should use the right Content-Type header

#### Known issue

When requesting for CSV or TSV, errors are returned in the same format, and thus are not easily readable.
If you use CSV or TSV, you should always check the HTTP status code to know if the request was successful or not.

""",
    "VERSION": "0.3.0",
    # OTHER SETTINGS
    "SERVERS": [
        {"url": BASE_URL, "description": f"{_ENV}: Where you got this schema."}
    ],
    "AUTHENTICATION_WHITELIST": [
        "firefighter.api.authentication.BearerTokenAuthentication"
    ],
    # Ignore drf-standardized-errors that all have the same name
    "ENUM_NAME_OVERRIDES": {
        "ValidationErrorEnum": "drf_standardized_errors.openapi_serializers.ValidationErrorEnum.values",
        "ClientErrorEnum": "drf_standardized_errors.openapi_serializers.ClientErrorEnum.values",
        "ServerErrorEnum": "drf_standardized_errors.openapi_serializers.ServerErrorEnum.values",
        "ErrorCode401Enum": "drf_standardized_errors.openapi_serializers.ErrorCode401Enum.values",
        "ErrorCode403Enum": "drf_standardized_errors.openapi_serializers.ErrorCode403Enum.values",
        "ErrorCode404Enum": "drf_standardized_errors.openapi_serializers.ErrorCode404Enum.values",
        "ErrorCode405Enum": "drf_standardized_errors.openapi_serializers.ErrorCode405Enum.values",
        "ErrorCode406Enum": "drf_standardized_errors.openapi_serializers.ErrorCode406Enum.values",
        "ErrorCode415Enum": "drf_standardized_errors.openapi_serializers.ErrorCode415Enum.values",
        "ErrorCode429Enum": "drf_standardized_errors.openapi_serializers.ErrorCode429Enum.values",
        "ErrorCode500Enum": "drf_standardized_errors.openapi_serializers.ErrorCode500Enum.values",
    },
    "POSTPROCESSING_HOOKS": [
        "drf_standardized_errors.openapi_hooks.postprocess_schema_enums"
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
        "docExpansion": "list",
        "filter": True,
        "showCommonExtensions": True,
        "tryItOutEnabled": True,
        "requestSnippetsEnabled": True,
        "requestSnippets": {
            "generators": {
                "curl_bash": {"title": "cURL (bash)", "syntax": "bash"},
                "curl_powershell": {
                    "title": "cURL (PowerShell)",
                    "syntax": "powershell",
                },
                "curl_cmd": {"title": "cURL (CMD)", "syntax": "bash"},
            },
            "defaultExpanded": False,
            "languages": None,
        },
    },
}
# DRF Standardized Errors
# https://drf-standardized-errors.readthedocs.io/en/latest/settings.html
DRF_STANDARDIZED_ERRORS = {
    # We removed 405, 406 and 415 from the OpenAPI schema: they should not appear if you follow the schema
    "ALLOWED_ERROR_STATUS_CODES": [
        "400",
        "401",
        "403",
        "404",
        "429",
        "500",
    ],
}


"Additional servers to add to the OpenAPI schema"
FF_API_SWAGGER_ADDITIONAL_SERVERS: list[dict[str, str | dict[str, dict[str, str]]]] = []


SPECTACULAR_SETTINGS.setdefault("SERVERS", []).extend(  # type: ignore[attr-defined]
    [
        server
        for server in FF_API_SWAGGER_ADDITIONAL_SERVERS
        if server.get("url") != BASE_URL
    ]
)
