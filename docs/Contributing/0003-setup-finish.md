
# Setup your Dev environment to work in Docker

The Docker setup is made if you don't want to mess with Python versions and dependencies on your machine.

It will also launch the dependencies in Docker (Redis, Postgres).

## Set your .env (part 2)

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

## Apply the migrations

```shell
pdm run migrate
```

> This PDM command uses the [`migrate`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#migrate) command of Django to apply migrations on all enabled applications.
> If you enable a new app (switch PagerDuty on for the first time for instance), you'll need to apply migrations again.

## Create a superuser (back-office admin)

```shell
pdm run createsuperuser
```

> This PDM command will use the env variables set earlier (`DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_USERNAME` and `DJANGO_SUPERUSER_PASSWORD`) to create an admin user.
> Tou can use this user to login at <http://127.0.0.1:8080/admin/>

## Load fixtures

```shell
pdm run loaddata
```

> This PDM command uses the [`loaddata`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#loaddata) command of Django to gather necessary objects (Severities, Components, Groups...)

## Launch the server

```shell
pdm run runserver
```

> This PDM command uses the [`runserver`](https://docs.djangoproject.com/en/4.2/ref/django-admin/#runserver) command of Django.

## Test everything is working

- Go to your <https://127.0.0.1:8080>
- Go to the BackOffice <https://127.0.0.1:8080/admin/>
- Submit your command in Slack
