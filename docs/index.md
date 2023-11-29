{%
   include-markdown "../README.md"
%}

## Design guidelines

- All actions taking place during the incident resolution must be able to be done via the Slack App.
  - Some of these actions may be doable through other means (e.g.: opening an incident through Slack, but also API or Web UI.)
- Actions taking place after the incident resolution may be done through the Web UI, API or Back-Office.

# Caveats

FireFighter is an internal tool, and works great for us, but may not be suitable for your use case.

## Performance

FireFighter has not be built with performance in mind, and may not scale well.

The goal is still to have response times under 1s, to provide a decent user experience, for all user interfaces (Slack, Web UI).

API and Back-Office are not as critical, and may be slower.

Nevertheless, we have been able to handle incidents with hundreds of messages, and hundreds of users, without any issue.

If you have any important performance issue, please open an issue, and we will try to help.

## Back-Office

The current back-office works great, but lacks many safety features, and must be handled with caution.
It is necessary to access it to configure some features (e.g.: define a metric type or cost type)

## API

The API is almost exclusively read-only, and is useful for read-only integrations and reporting.
The API is not exhaustive, and is missing models and fields.
Most GET routes supports filtering, ordering, and rendering in JSON, CSV or TSV.

There is an API route to create an incident, if you want to integrate with other systems.
All routes support Cookie and API Key authentication.

Please check the OpenAPI schema or Swagger UI for more information.

## Web UI

The Web-UI supports authentication (for us, with OpenID Connect), and is the main way to interact with the system.

No authentication is required to access pages, only to create or update.

The Web-UI was built with progressive enhancement in mind, and should work without JavaScript, although the experience will be degraded.

The Web-UI has not yet been tested with screen readers, and may not be accessible.

The Web-UI is not regularly tested with mobile devices, and may not provide a good experience on small screens or screens with unusual aspect ratios.

## Integrations

### Slack

The Slack App is the main way to interact with the system, and is the only way to interact with the system during an incident.
Supporting other chat platforms is not planned, but may be possible with some work.

Slack is currently also used as the user directory.

We currently only support one workspace, and do not support enterprise grid.

We don't support Slack OAuth.

### Other systems

The application integrates with Confluence, PagerDuty and Jira.
Providing more integrations is not planned, but we plan to help integrate with other systems, by exposing Python APIs and hooks.

> This means that the runbook or postmortem back-end can only be Confluence, the ticketing system can only be Jira, and the alerting system can only be PagerDuty, for now.
> If you want to use other systems, you will have to integrate with them yourself.
> Please open an issue if you need help with that.


## Roadmap

- Better deployment documentation and tooling
  - Simple use-case: no custom code
    - Ready to use Docker images
    - Ready to use Helm charts?
  - Advanced use-case: custom code or configuration
    - How to build custom Docker images?
  - Less opinionated deployment, more configuration options
- Subscription system
  - Users should be able to create their own rules to subscribe to incidents, and receive notifications
  - Notifications should use default integrations, but may also integrate [apprise](https://github.com/caronc/apprise)
- More integrations
  - We need give a way to extended the system, but **won't implement these** ourselves
  - More ticketing systems
    - Jira Service Desk
    - Zendesk
    - ...
  - More document platforms
    - Google Docs
    - ...
  - More monitoring systems
    - Prometheus
    - ...
  - Support for other authentication methods
    - LDAP
    - SAML
    - ...
  - Support for other messaging platforms?
    - Mattermost
    - Discord
    - ...
- Rework IncidentUpdate system
- Rework audit log system
- Metrics export
- i18n and l10n
  - Basic support planned
- Technical upgrades
  - Django 5.0
    - Prepare for Django 5.0
    - Study ASGI/partial move to async
      - Would unlock direct connect to SLack instead of opening a port
      - May be blocked by dependencies (e.g.: DRF is sync-only)
  - JS/CSS automatic building and bundling
  - HTMX/Alpine upgrade
- Better testing
  - E2E Web UI tests
  - Better integration (Slack, Confluence, Jira, PagerDuty) tests
- Support for rich text
  - Either markdown or HTML, adapted to work both on Web UI and Slack

## Versioning, compatibility and support

## Python and Django versions

At the moment, we provide no guarantees regarding compatibility and support.

We currently support one version of Django and Python, and one version of PostgreSQL and Redis.

We plan to follow the latest versions of Django and Python, if possible.

We may expand the list of supported versions of Python or Django in the future, but don't plan to support older versions.

## FireFighter versions

We plan to follow semantic versioning, and provide a changelog.

However, we may break compatibility between minor versions, and don't plan to support older versions.

Please check the changelog before upgrading.
