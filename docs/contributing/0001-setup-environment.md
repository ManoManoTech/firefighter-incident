
# Setup your Dev environment

The following documentation assume your system meet the [prerequisites](0000-prerequisites.md).

## Clone the repository

```shell
git clone git@github.com:ManoManoTech/firefighter-incident.git
cd firefighter-incident
```

## Load ASDF/Mise/Direnv _(optional)_

If you use ASDF, Mise (previously rtx) or Direnv, you can load the environment with:

```shell
asdf install
# or
mise install
# then
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

You can start up the Postgres and Redis dependencies, apply migrations, load fixtures, create a superuser and collect static files with one shortcut:

```shell
pdm run dev-env-setup
```


??? question "What does it do?"
    It will perform the following steps:

    1. Launch dependencies with Docker


    ```shell
    docker-compose up -d db redis
    ```

    2. Apply the database migrations

    ```shell
    pdm run migrate
    ```

    > This PDM command uses the [`migrate`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#migrate) command of Django to apply migrations on all enabled applications.
    > If you enable a new app (switch PagerDuty on for the first time for instance), you'll need to apply migrations again.

    3. Load fixtures

    ```shell
    pdm run loaddata
    ```

    > This PDM command uses the [`loaddata`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#loaddata) command of Django to gather necessary objects (Severities, Components, Groups...)

    4. Create a superuser

    ```shell
    pdm run createsuperuser
    ```

    > This PDM command will use the env variables set earlier (`DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD`) to create an admin user.
    > Tou can use this user to login at <http://127.0.0.1:8080/admin/>

    5. Collect static files

    ```shell
    pdm run collectstatic
    ```

## Run the server

You should now be able to run the server locally with:

```shell
pdm runserver
```

> This PDM command uses the [`runserver`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#runserver) command of Django.

You can login at http://127.0.0.1:8000/admin/ with the superuser you created.

!!! warning
    If you run the server at this stage, you can expect some warnings/errors.
