
# Setup your Dev environment

The following documentation assume your system meet the [prerequisites](0000-prerequisites.md).

## Set your .env (part 1)

First, **copy** the `.env.example` to `.env` and edit it.

The first part of the `.env` is just your choice of local development, and dependencies connection details.

Make sure the following environment variables are set in the `.env` file:

```bash title=".env (sample)"
TOOLS_COMMON_PGDB_HOST=localhost
INFRA_FIREFIGHTER_V2_CACHE_HOST=localhost
```

## Local development setup

### Install PDM

!!! note "TLDR"

    - If you have [pipx](https://pypa.github.io/pipx/installation/) installed, you can use it to install PDM: `pipx install pdm`
    - If you don't, install pipx then PDM `pip install --user pipx && pipx install pdm`

> Consider using ASDF or RTX instead.

## Launch dependencies

If you only want the Redis and Postgres run with Docker

```shell
docker-compose up -d db redis
```

> If you run the server at this stage, you can expect some warnings/errors.
