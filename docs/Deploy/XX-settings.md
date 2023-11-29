# Settings

Most of the settings are loaded through environment variables.

Other settings may be set using a custom settings module. XXX link

> The exposed settings are not guaranteed to be stable. We may change them at any time.
> We will try to avoid breaking changes, but we may not be able to avoid them.

## Settings reference

### Database settings

`POSTGRES_DB`
`POSTGRES_USER`
`POSTGRES_PASSWORD`
`POSTGRES_HOST`
`POSTGRES_PORT`

### Redis settings

`REDIS_HOST`
`REDIS_PORT`

Redis DBs:

- 0 for default
- 1 for sessions
- 2 for cache
- 10 for celery

## FireFighter settings

`FF_ROLE_REMINDER_MIN_DAYS_INTERVAL`
`PLAUSIBLE_DOMAIN`
`PLAUSIBLE_SCRIPT_URL`

## SSO OIDC settings

See
<!-- XXX Add link to dedicated doc -->

OIDC_OP_DISCOVERY_DOCUMENT_URL
OIDC_UNUSABLE_PASSWORD
OIDC_RP_USE_PKCE
OIDC_RP_CLIENT_ID
OIDC_RP_CLIENT_SECRET
OIDC_TIMEOUT

## Debug settings

`DEBUG_TOOLBAR`

## Slack integration

<!-- XXX OSS -->

## Confluence integration

`ENABLE_CONFLUENCE`

<!-- XXX OSS -->

## Pagerduty integration

`ENABLE_PAGERDUTY`
<!-- XXX OSS -->
## Other settings

### Django

`CSRF_TRUSTED_ORIGINS`
`TIME_ZONE`
`SECRET_KEY`

## Mapping environment variables

k/v pairs separated by `,` and `:`

`FF_ENV_VAR_MAPPING=FIREFIGHTER_NAME:MY_CUSTOM_ENV_VAR_NAME,FIREFIGHTER_OTHER_NAME:MY_OTHER_CUSTOM_ENV_VAR_NAME`

Useful for mapping environment variables to the ones used by FireFighter.

!!! warning
    Content of the target environment variables will be overwritten.
