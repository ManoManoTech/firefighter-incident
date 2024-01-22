{%
   include-markdown "../README.md"
   rewrite-relative-urls=false
   end="<!--intro-end-->"
%}

## Features

<div class="grid cards" markdown>

-   :fontawesome-brands-slack:{ .lg .middle } __Slack first__

    ---

    Don't leave Slack to manage incidents, and keep your team in the loop.

    <!-- [:octicons-arrow-right-24: Slack App](#) -->

    <!-- [:octicons-arrow-right-24: Getting started](#) -->

-   :simple-pagerduty:{ .lg .middle }  __Forward to PagerDuty__ _(optional)_

    ---

    Expose your on-call schedule, and allow anyone to escalate to PagerDuty.

    [:octicons-arrow-right-24: Learn more](Usage/integrations.md#pagerduty)

-   :fontawesome-brands-jira:{ .lg .middle } __Follow on Jira__ _(optional)_

    ---

    Create a Jira ticket for the incident, and follow the incident from Jira.

-   :fontawesome-brands-confluence:{ .lg .middle } __Manage Confluence documents__ _(optional)_

    ---

    Automatically create a Post-mortem on Confluence, and sync your runbooks.

-   :fontawesome-solid-puzzle-piece:{ .lg .middle } __Extend with the API__

    ---

    Integrate with other systems, and extend the application with the API.
</div>

!!! warning "Young project disclaimer"

    FireFighter was only recently open-sourced, and is still a work in progress.

    While we are working on improving the documentation, and making the application more generic, there are still some caveats and FireFighter may not be ready for you yet.

    Python and Django knowledge is still recommended to install, configure and troubleshoot the application.

    Please open an issue if you have any question, or if you need help.

    The [FAQ](FAQ.md) may also answer some of your questions.
