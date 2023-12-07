
# Roadmap

The following is a list of features we plan to implement in the future.

This list is not exhaustive, and may change at any time. There is no guarantee that any of these features will be implemented, it is only provided as a way of showing intent.

- Better deployment documentation and tooling
  - Simple use-case: no custom code
    - [X] Ready to use Docker images
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
