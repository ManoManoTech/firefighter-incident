# Set up the Slack app

You **need** to have a working Slack integration for FireFighter to work. Other integrations (PagerDuty, Confluence, ...) are optional.

## Slack App setup

To use FireFighter, you'll need to have a working Slack App (*aka Slack Bot*) for your dev environment, and a way to expose it to the internet.

### Expose your local stack on the internet

You need to make your local instance reachable by Slack servers, using a tool like [expose](https://expose.dev/), [ngrok](https://ngrok.com/) or [Localtunnel](https://theboroer.github.io/localtunnel-www/).

Launch your local tunnel and note your URL.

> It's best if you have a stable URL, so you don't have to update your Slack app every time you restart your tunnel.

## Choose your development Slack Workspace

> For development purposes, we recommend creating a dedicated workspace.

If you don't have one yet, you can [create your own Slack workspace](https://slack.com/get-started#/createnew) for testing.

## Create your own Slack app and install it to your workspace

Before creating your app, make sure you have a workspace to develop your app.

Then, go to [Slack application creation page](https://api.slack.com/apps?new_app=1) and `Create a new app`.

=== "Generate your manifest _(recommended)_"
    We provide a command to generate a manifest for you, with the correct values.

    First, make sure your variables to choose the command name are set:

    ```shell
    SLACK_INCIDENT_COMMAND="/<your-command-name>" # required
    SLACK_INCIDENT_COMMAND_ALIASES="/alias-1,/alias_abc" # optional
    ```
    Then run
    ```shell
    ff-manage generate_manifest --public-url https://your-local-tunnel-url
    ```
    > Alternatively, use `pdm run manage generate_manifest`. You can check the options with `--help`.

    This will generate a manifest in stdout. You can copy it and paste it in the Slack App creation page.

=== "Edit a pre-generated manifest"
    If you can't generate the manifest using the Django management command, you can try to copy the following manifest and change a few values.

    1. Change the 3 links to your local URL (`https://<YOUR_LOCAL_STACK>/api/v2/firefighter/slack/incident`)
    2. Preferably, change the command in `features > slash_commands > command` to avoid duplicates.
      - It is not needed if you use your own workspace, and not other Slack app uses `/incident` there.
      - Hence, it is needed in the Team FireFighter workspace, as the INT environment uses this workspace.
      - `{YOUR_NAME}-incident` seems like a good idea
      - Put the same command in your `.env` file, in `SLACK_INCIDENT_COMMAND`

    ```yaml
    _metadata:
      major_version: 1
      minor_version: 1
    display_information:
      name: FireFighter DEV {YOUR_NAME}
      description: Incident Management Bot
      background_color: "#c84146"
    features:
      app_home:
        home_tab_enabled: true
        messages_tab_enabled: false
        messages_tab_read_only_enabled: false
      bot_user:
        display_name: FireFighter [{YOUR_NAME} DEV] - Incident
        always_online: true
      shortcuts:
        - name: Open incident {YOUR_NAME}
          type: global
          callback_id: open_incident
          description: Open an incident and get help
      slash_commands:
        - command: /{YOUR-NAME}-incident
          url: https://<YOUR_LOCAL_STACK>/api/v2/firefighter/slack/incident/
          description: Manage Incidents 🚨
          usage_hint: "[open|update|close|status|help]"
          should_escape: false
    oauth_config:
      scopes:
        bot:
          - bookmarks:write
          - channels:history
          - channels:join
          - channels:manage
          - channels:read
          - chat:write
          - chat:write.customize
          - chat:write.public
          - commands
          - groups:history
          - groups:read
          - groups:write
          - im:read
          - im:write
          - mpim:read
          - pins:read
          - pins:write
          - usergroups:read
          - users.profile:read
          - users:read
          - users:read.email
          - usergroups:write
    settings:
      event_subscriptions:
        request_url: https://<YOUR_LOCAL_STACK>/api/v2/firefighter/slack/incident/
        bot_events:
          - app_home_opened
          - channel_archive
          - channel_id_changed
          - channel_rename
          - channel_unarchive
          - group_archive
          - group_rename
          - group_unarchive
      interactivity:
        is_enabled: true
        request_url: https://<YOUR_LOCAL_STACK>/api/v2/firefighter/slack/incident/
      org_deploy_enabled: false
      socket_mode_enabled: false
      token_rotation_enabled: false
    ```

## Get the required tokens and IDs from Slack

Finally, make sure that your app is installed in your Slack Workspace.

FireFighter is a "dumb" app, so you have to provide some values.

You will set the following environment variables in your `.env` file:

- `SLACK_SIGNING_SECRET`: The Slack signing secret (Slack API > Your App Page > Settings > Basic Information)
- `SLACK_BOT_TOKEN`: Bot User OAuth Token (in Slack API > Your App Page > Features > OAuth & Permissions)
    - *It should start with `xoxb-`*

You may want to add in the DB some conversations:

- An equivalent of #tech-incidents, with the tag `tech_incidents`
- An equivalent of #it-deploy, with the tag `it_deploy`


## Review your settings

Check the `.env`.

Read the settings page.

Once Slack is setup, you can remove FF_SKIP_SLACK_CHEKS=true from your `.env` file.

Using the information from the previous part, check your configuration.

> At the moment, we have no PagerDuty or Confluence accounts to test the integration, Nevertheless the integrations can be disabled.

```bash title=".env"
--8<--
.env.example
--8<--
```

1. These environment variables are not loaded by Python/Django, and are only used for bash scripts and Makefiles.
   Make sure there are no spaces or quotes in the values.
2. - `dev`
   - `test`
   - `prd`, `int`, `support`, `prod` are equivalent for the app (not for Datadog!)
3. If you enable the Confluence integration **all** environments variables must be set. If you disable it, no variables will be loaded.
4. If you enable the PagerDuty integration, you **must** set the `PAGERDUTY_API_KEY` and `PAGERDUTY_ACCOUNT_EMAIL` environment variables. If you disable it, no variables will be loaded.

## Check everything is working

> If you stopped the server, you can restart it with `pdm run runserver`.

- Go to your <https://127.0.0.1:8000>
- Go to the BackOffice <https://127.0.0.1:8000/admin/>
- Submit your command in Slack
