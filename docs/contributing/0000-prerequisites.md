# Development environment pre-requisites

- [Python 3.12](https://www.python.org/downloads/)
- [Node 18+](https://nodejs.org/en/download)
- [PDM 2.24+](https://pdm-project.org/latest/)
- [Docker](https://docs.docker.com/engine/install/)
- [Docker-compose](https://github.com/docker/compose?tab=readme-ov-file#where-to-get-docker-compose)
- A Slack workspace with sufficient permissions to create apps and install them
  - We recommend creating a dedicated workspace for development purposes
  - For testing environments without usergroups, see [Test Environment Configuration](#test-environment-configuration)
- A tunnel to your local machine (e.g. [expose](https://expose.dev/), [ngrok](https://ngrok.com/) or [Localtunnel](https://theboroer.github.io/localtunnel-www/)) to receive Slack events
- [pre-commit](https://pre-commit.com/#install) _(optional, recommended)_
- [mise (previously rtx)](https://github.com/jdx/mise) _(optional, strongly recommended)_
  - You can install and manage versions of Python, Node, PDM, etc. with this tool
  - Alternative: [asdf](https://asdf-vm.com/#/core-manage-asdf-vm)

## Test Environment Configuration

If you're testing on a Slack workspace without usergroups (like `manomano-test`), you'll need specific configuration:

### Required Environment Variables

```bash
# Test mode configuration
TEST_MODE=True
ENABLE_SLACK_USERGROUPS=False
APP_DISPLAY_NAME="IMPACT[TEST]"

# Your test Slack command
SLACK_INCIDENT_COMMAND=/your-test-incident
```

### Benefits of Test Mode

- ✅ **Works with any user ID**: Automatic creator invitation to incident channels
- ✅ **No usergroup errors**: Skips Slack usergroup invitations when not available  
- ✅ **Realistic testing**: Maintains all core functionality while adapting to test environment limitations

This configuration allows you to test the full incident creation workflow without requiring Slack usergroups to be set up in your test workspace.
