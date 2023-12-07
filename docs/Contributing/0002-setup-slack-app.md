# Set up the Slack app

You **need** to have a working Slack integration for FireFighter to work. Other integrations (PagerDuty, Confluence, ...) are not mandatory.

## Summary

1. Launch a localtunnel (to expose a port on your machine to the Slack API with HTTPS)
2. Create a Slack App
3. Add it to a test Slack Workspace
4. Complete your .env files with Slack API keys

## Slack API setup

To use FireFighter, you'll need to have a working Slack App (*aka Slack Bot*) for your dev environment.

### Expose your local stack on the internet

You need to make your local instance reachable by Slack servers.
For example use [localtunnel](https://theboroer.github.io/localtunnel-www/) (recommended) or ngrok (beware, subdomains are temporary!).
You can choose any subdomain you want, lowercase only.

Once installed, you can start your local tunnel either way with `lt --port 8000 --subdomain <YOUR_SUDOMAIN_>` or any other tool you prefer.

Localtunnel will print you your URL.

## Choose your development Slack Workspace

> Please do not use the "real" ManoMano Slack for your day-to-day development.

Instead, you can use the Team FireFighter workspace, dedicated to develop and test the bot. Please ask the Pulse team for an invitation or [try this link](https://team-firefighter.slack.com/join/signup)

If you choose, you can also [create your own Slack workspace](https://slack.com/get-started#/createnew) for testing.

## Create your own Slack app and install it to your workspace

Before creating your app, make sure you have a workspace to develop your app.

Then, go to [Slack application creation page](https://api.slack.com/apps?new_app=1) and `Create a new app`.

To create the app from a manifest, you only need to copy the following manifest and change a few values.

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
