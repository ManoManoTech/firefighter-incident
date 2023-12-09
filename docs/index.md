{%
   include-markdown "../README.md"
   rewrite-relative-urls=false
   end="<!--intro-end-->"
%}


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
