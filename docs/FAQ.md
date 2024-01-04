# Frequently Asked Questions

## Is FireFighter performant?

FireFighter has not be built with performance in mind, and may not scale well.

The goal is still to have response times under 1s, to provide a decent user experience, for all user interfaces (Slack, Web UI).

API and Back-Office are not as critical, and may be slower.

Nevertheless, we have been able to handle incidents with hundreds of messages, and hundreds of users, without any issue.

If you have any important performance issue, please open an issue, and we will try to help.

## Is FireFighter secure?

We hope so! We have tried to follow best practices, but we don't provide any warranty.

> If you find a security issue, [please report it to our security team](https://github.com/ManoManoTech/firefighter-incident/security/policy#reporting-a-vulnerability).

## Is FireFighter production-ready?

FireFighter is currently used in production by ManoMano, and has been used to handle thousands of incidents.

Nevertheless, it was only recently open-sourced, and we are still working on improving the documentation, test coverage, and making the application more generic.

## Can I use FireFighter without Slack?

No. Slack is currently the only supported chat platform.

The Slack App is the main way to interact with the system, and is the only way to interact with the system during an incident. Slack is currently also used as the user directory.

## Can I use FireFighter only through Slack?

No. The Web UI is required to interact with the application, and is the only way to configure the application.

All incident-related actions during an incident can be done through Slack.

## Can I use FireFighter without PagerDuty?

Yes.

## Can I use FireFighter without Confluence?

Yes.

## Can I use FireFighter without Jira?

Yes.

## Can I use _other provider_?

Not yet.

The application integrates with Slack, Confluence, PagerDuty and Jira.
Providing more integrations is not planned, but we plan to help integrate with other systems, by exposing Python APIs and hooks.

> This means that the runbook or postmortem back-end can only be Confluence, the ticketing system can only be Jira, and the alerting system can only be PagerDuty, for now.
> If you want to use other systems, you will have to integrate with them yourself.
> Please open an issue if you need help with that.

## Can I interact with FireFighter through the API?

Yes.

The API is almost exclusively read-only, and is useful for read-only integrations and reporting.
The API is not exhaustive, and is missing models and fields.
Most GET routes supports filtering, ordering, and rendering in JSON, CSV or TSV.

There is an API route to create an incident, if you want to integrate with other systems.
All routes support Cookie and API Key authentication.

Please check the OpenAPI schema or Swagger UI for more information.

## Can I give access to the Back-Office to non-admin users?

The current back-office works great, but lacks many safety features, and must be handled with caution.
It is necessary to access it to configure some features (e.g.: define a metric type or cost type).

Thus, we recommend only giving access to the Back-Office to trusted users.

## What authentication methods are supported?

The Web UI supports OpenID Connect, and can be configured to use any OIDC provider.

## Is the Web UI accessible? Responsive? Reliable?

The Web-UI was built with progressive enhancement in mind, and should work without JavaScript, although the experience will be degraded.

The Web-UI has not yet been tested with screen readers, and may not be accessible.

The Web-UI is not regularly tested with mobile devices, and may not provide a good experience on small screens or screens with unusual aspect ratios.

> If you have any accessibility issue, please open an issue, and we will try to help.

## Do you support Slack Enterprise Grid?

No. We only support one workspace, and do not support Enterprise Grid.

> If you need support for Enterprise Grid, please open an issue, and we will try to help.

## Do you support free Slack workspaces?

Yes. We support free Slack workspaces, but we some features may not work (e.g. usergroups are not supported).

## Do you support Slack OAuth?

No. We don't support Slack OAuth.
