
# Setup your Dev environment

The following documentation assume your system meet the [prerequisites](0000-prerequisites.md).

## Clone the repository

```shell
git clone git@github.com:ManoManoTech/firefighter-incident.git
cd firefighter-incident
```

## Load ASDF/RTX/Direnv _(optional)_

If you use ASDF, RTX or Direnv, you can load the environment with:

```shell
asdf install
# or
rtx install
direnv allow
```

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

The first part of the `.env` is just your choice of local development, and dependencies connection details.

Make sure to set the `SECRET_KEY` to a random string.

You can already fill `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD` to create a superuser.

## Setup everything

The following steps can be run with:
```shell
pdm run dev-env-setup
```

It will performan the following steps:

### 1. Launch dependencies with Docker


```shell
docker-compose up -d db redis
```

### 2. Migrate the database

```shell
pdm run migrate
```

### 3. Load fixtures

```shell
pdm run loaddata
```

### 4. Create a superuser

```shell
pdm run createsuperuser
```

### 5. Collect static files

```shell
pdm run collectstatic
```

## You should now be able to run the server

```shell
pdm runserver
```

You can login at http://127.0.0.1:8000/admin/ with the superuser you created.


> If you run the server at this stage, you can expect some warnings/errors.
