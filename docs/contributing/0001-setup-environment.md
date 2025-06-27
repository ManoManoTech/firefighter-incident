
# Setup your Dev environment

The following documentation assume your system meet the [prerequisites](0000-prerequisites.md).

## Clone the repository

```shell
git clone git@github.com:ManoManoTech/firefighter-incident.git
cd firefighter-incident
```

## Load Mise/ASDF/Direnv _(strongly recommended)_

We use [Mise](https://mise.jdx.dev/) to manage tool versions (Python, Node, PDM) and automate environment setup.

### Using Mise (Recommended)

```shell
# Install all tools defined in mise.toml
mise install

# This will automatically:
# - Install Python 3.12
# - Install Node 18
# - Install PDM 2.24.1
# - Install act (for local GitHub Actions testing)
# - Run post-install hooks (pdm sync)
```

### Alternative: ASDF + Direnv

```shell
asdf install
# then
direnv allow
```

### What Mise Does Automatically

The `mise.toml` configuration includes:

- **Tool versions**: Python 3.12, Node 18, PDM 2.24.1, ACT 0.2.77
- **Post-install hook**: Automatically runs `pdm sync` after tool installation
- **Environment management**: Virtual environment creation and activation
- **Task runner**: Includes lint task (`mise run lint`)

### Manual Installation (Not Recommended)

If you prefer not to use Mise, ensure you have the correct versions:
- Python 3.12
- Node 18+  
- PDM 2.24+

## Install dependencies with PDM

> We assume you have `pdm` in your path. If you have installed it with `pipx`, you can use `pipx run pdm` instead.

```shell
pdm install
```

A new virtualenv will be created in `.venv` and dependencies will be installed.

## Activate your venv

While you can use `pdm run` to run commands, you can also activate your venv with:

```shell
source .venv/bin/activate
```

## Install pre-commit hooks _(optional)_

```shell
pre-commit install
```

## Set your .env

First, **copy** the `.env.example` to `.env` and edit it.

```shell
cp .env.example .env
```

### Required Configuration

Make sure to set these essential variables:

```bash
# Security
SECRET_KEY="your-random-secret-key-here"

# Superuser for Django admin
DJANGO_SUPERUSER_EMAIL=you@example.com
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_PASSWORD=your-password

# Slack integration (required)
SLACK_INCIDENT_COMMAND="/your-incident"
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
```

### Test Environment Configuration

If you're testing on a Slack workspace without usergroups:

```bash
# Test mode - skips usergroup invitations
TEST_MODE=True
ENABLE_SLACK_USERGROUPS=False
APP_DISPLAY_NAME="FireFighter[TEST]"

# Your test command name
SLACK_INCIDENT_COMMAND=/test-incident
```

### Optional Integrations

You can disable optional integrations during development:

```bash
# Disable optional integrations
ENABLE_CONFLUENCE=False
ENABLE_PAGERDUTY=False
ENABLE_RAID=False

# Skip Slack validation during development
FF_SLACK_SKIP_CHECKS=true

# Disable SSO redirect for local development
FF_DEBUG_NO_SSO_REDIRECT=true
```

## Setup everything

You can start up the Postgres and Redis dependencies, apply migrations, load fixtures, create a superuser and collect static files with one shortcut:

```shell
pdm run dev-env-setup
```

### Alternative: Step-by-step Setup

If you prefer to run each step manually or need to troubleshoot:

```shell
# 1. Start Docker services
pdm run dev-env-start

# 2. Apply database migrations  
pdm run migrate

# 3. Load fixture data (priorities, components, groups, etc.)
pdm run loaddata

# 4. Create superuser
pdm run createsuperuser

# 5. Collect static files
pdm run collectstatic

# 6. Build web assets (CSS/JS)
pdm run build-web
```

### New PDM Scripts Available

Since the system overhaul, we've added many new PDM scripts:

**Environment Management:**
- `dev-env-setup` - Complete environment initialization
- `dev-env-start` - Start Docker services only
- `dev-env-stop` - Stop Docker services  
- `dev-env-destroy` - ⚠️ Destroy environment (including database!)

**Development:**
- `build-web` - Build CSS/JS assets with Rollup/Tailwind
- `runserver` - Start Django development server
- `celery-worker` - Start Celery worker for background tasks
- `celery-beat` - Start Celery beat scheduler

**Documentation:**
- `docs-serve` - Serve documentation locally with MkDocs
- `docs-build` - Build documentation for production

**Code Quality:**
- `fmt` - Run all formatters (ruff, djhtml)
- `lint` - Run all linters (ruff, pylint, mypy)
- `tests` - Run test suite
- `tests-cov` - Run tests with coverage report

??? question "What does dev-env-setup do?"
    It will perform the following steps:

    1. Launch dependencies with Docker
    ```shell
    docker-compose up -d db redis
    ```

    2. Apply the database migrations
    ```shell
    pdm run migrate
    ```
    > This applies migrations for all enabled applications, including new component/priority system migrations.

    3. Load fixtures
    ```shell
    pdm run loaddata
    ```
    > Loads priorities, components, groups, impact levels, and Slack usergroup mappings.

    4. Create a superuser
    ```shell
    pdm run createsuperuser
    ```
    > Uses environment variables (`DJANGO_SUPERUSER_*`) to create an admin user.

    5. Collect static files
    ```shell
    pdm run collectstatic
    ```

    6. Build web assets
    ```shell
    pdm run build-web
    ```
    > Compiles Tailwind CSS and bundles JavaScript with Rollup.

## Run the server

You should now be able to run the server locally with:

```shell
pdm runserver
```

> This PDM command uses the [`runserver`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#runserver) command of Django.

You can login at http://127.0.0.1:8000/admin/ with the superuser you created.

!!! warning
    If you run the server at this stage, you can expect some warnings/errors.
    
    At the moment, we have no PagerDuty or Confluence accounts to test the integration. Nevertheless, the integrations can be disabled by setting `ENABLE_PAGERDUTY=False` and `ENABLE_CONFLUENCE=False` in your `.env` file.
