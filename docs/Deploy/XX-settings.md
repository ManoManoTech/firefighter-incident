# Settings

Most of the settings are loaded through environment variables.

Other settings may be set using a [custom settings module](XX-custom-settings.md).

> The exposed settings are not guaranteed to be stable. We may change them at any time.
> We will try to avoid breaking changes, but we may not be able to avoid them.

## Settings reference

### Database settings (_required_)

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

### Redis settings (_required_)

- `REDIS_HOST`
- `REDIS_PORT`

Redis DBs:

- `0` for default
- `1` for sessions
- `2` for cache
- `10` for celery

## FireFighter settings



- [`BASE_URL`][firefighter.firefighter.settings.settings_utils.BASE_URL]
- [`FF_ROLE_REMINDER_MIN_DAYS_INTERVAL`][firefighter.firefighter.settings.components.common.FF_ROLE_REMINDER_MIN_DAYS_INTERVAL]
- [`FF_USER_ID_HEADER`][firefighter.firefighter.settings.components.common.FF_USER_ID_HEADER]
- [`FF_OVERRIDE_MENUS_CREATION`][firefighter.firefighter.settings.components.common.FF_OVERRIDE_MENUS_CREATION]
- [`FF_DEBUG_ERROR_PAGES`][firefighter.firefighter.settings.components.common.FF_DEBUG_ERROR_PAGES]
- [`FF_DEBUG_ERROR_PAGES`][firefighter.firefighter.settings.components.common.FF_DEBUG_ERROR_PAGES]
- [`FF_SKIP_SECRET_KEY_CHECK`][firefighter.firefighter.settings.components.common.FF_SKIP_SECRET_KEY_CHECK]
- [`FF_EXPOSE_API_DOCS`][firefighter.firefighter.settings.components.common.FF_EXPOSE_API_DOCS]
- `PLAUSIBLE_DOMAIN`
- `PLAUSIBLE_SCRIPT_URL`

## SSO OIDC settings

See [django-oauth2-codeflow](https://gitlab.com/systra/qeto/lib/django-oauth2-authcodeflow#full-configuration) documentation for more details.

- `OIDC_OP_DISCOVERY_DOCUMENT_URL`: url to the well-known OIDC discovery document
- `OIDC_UNUSABLE_PASSWORD`: default: `False`
- `OIDC_RP_USE_PKCE`: default: `False`
- `OIDC_RP_CLIENT_ID`: _required_
- `OIDC_RP_CLIENT_SECRET`: _required_
- `OIDC_TIMEOUT`: timeout in seconds for OIDC requests (default: 15s)

## Debug settings

`DEBUG_TOOLBAR`

## Slack integration

### Required settings

- [`SLACK_BOT_TOKEN`][firefighter.firefighter.settings.components.slack.SLACK_BOT_TOKEN]
- [`SLACK_SIGNING_SECRET`][firefighter.firefighter.settings.components.slack.SLACK_SIGNING_SECRET]
- [`SLACK_INCIDENT_COMMAND`][firefighter.firefighter.settings.components.slack.SLACK_INCIDENT_COMMAND]: default: `/incident`

### Optional settings

- [`SLACK_POSTMORTEM_HELP_URL`][firefighter.firefighter.settings.components.slack.SLACK_POSTMORTEM_HELP_URL]
- [`SLACK_INCIDENT_COMMAND_ALIASES`][firefighter.firefighter.settings.components.slack.SLACK_INCIDENT_COMMAND_ALIASES]: default: ``
- [`SLACK_INCIDENT_HELP_GUIDE_URL`][firefighter.firefighter.settings.components.slack.SLACK_INCIDENT_HELP_GUIDE_URL]
- [`SLACK_SEVERITY_HELP_GUIDE_URL`][firefighter.firefighter.settings.components.slack.SLACK_SEVERITY_HELP_GUIDE_URL]
- [`SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL`][firefighter.firefighter.settings.components.slack.SLACK_EMERGENCY_COMMUNICATION_GUIDE_URL]
- [`SLACK_EMERGENCY_USERGROUP_ID`][firefighter.firefighter.settings.components.slack.SLACK_EMERGENCY_USERGROUP_ID]
- [`SLACK_APP_EMOJI`][firefighter.firefighter.settings.components.slack.SLACK_APP_EMOJI]
- [`FF_SLACK_SKIP_CHECKS`][firefighter.firefighter.settings.components.slack.FF_SLACK_SKIP_CHECKS]

## Confluence integration

`ENABLE_CONFLUENCE`


## Pagerduty integration

- `ENABLE_PAGERDUTY`: default: `False`
- `PAGERDUTY_API_KEY`
- `PAGERDUTY_ACCOUNT_EMAIL`
- `PAGERDUTY_URL`: default: `https://api.pagerduty.com`

## Other settings

### Django

- [`CSRF_TRUSTED_ORIGINS`][CSRF_TRUSTED_ORIGINS]
- [`TIME_ZONE`][TIME_ZONE]
- [`SECRET_KEY`][SECRET_KEY]

## Mapping environment variables

k/v pairs separated by `,` and `:`

`FF_ENV_VAR_MAPPING=FIREFIGHTER_NAME:MY_CUSTOM_ENV_VAR_NAME,FIREFIGHTER_OTHER_NAME:MY_OTHER_CUSTOM_ENV_VAR_NAME`

Useful for mapping environment variables to the ones used by FireFighter.

!!! warning
    Content of the target environment variables will be overwritten.
