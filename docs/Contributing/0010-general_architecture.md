# General Architecture

FireFighter is built with Django 4.2+, and Python 3.11+.

## Apps

The project is built with multiple [Django apps](https://docs.djangoproject.com/en/4.2/ref/applications/).

## Custom apps

- [`firefighter`][firefighter.firefighter]
  - Main project package. Has the health-check URL, DB/Redis connections, all the settings... No features/models.
- [`incidents`][firefighter.incidents]
  - App containing all the incidents models and features, as well as the views.
- [`api`][firefighter.api]
  - App containing all the views for the FireFighter API. __Might be integrated in `incidents`__.
- [`slack`][firefighter.slack]
  - All Slack models and API.
  - As we are still coupled to Slack, this app unfortunately still a lot of business logic.
- [`confluence`][firefighter.confluence]
  - To read/write Confluence pages. Model for page.
- [`pagerduty`][firefighter.pagerduty]
  - Read PagerDuty on-call.
- [`raid`][firefighter.raid]
  - Non-critical incident (defects) management with Jira.

`confluence`, `pagerduty` and `api` can be disabled in the settings. `slack` is not, as you would lose too much functionality.

## Other apps

### Core-Django

- [django.contrib.admin][] to provide the back-office. (`/admin`)
- [django.contrib.admindocs][] to provide the automatic documentation. (`/admin/doc/`)
  - Useful to discover [all models and their related fields](http://127.0.0.1:8000/admin/doc/models/).
- [django.contrib.auth][] to provide basic auth with User, Group and Permissions.
- [django.contrib.contenttypes][] to track all models installed. Allows generic relations and much more.
- [django.contrib.messages][] to display notifications.
- [django.contrib.sessions][]
- [django.contrib.staticfiles][] to collect all static files and put them in a single directory.
  - Every app puts their assets in their own directory. They have to be regrouped to be served easily.
  - Serves assets in dev.
- [django.contrib.humanize][] to format in a more human ways numbers and dates.

### Dependencies

- `widget_tweaks` to customize form fields in templates. [Readme](https://github.com/jazzband/django-widget-tweaks)
- `rest_framework` to provide REST API features. [Extensive doc for Django Rest Framework](https://www.django-rest-framework.org/).
- `django_filters` to provide filtering on views or API endpoints. [Docs](https://django-filter.readthedocs.io/en/stable/).
- `django-taggit` to provide a TagManager on Incidents.
- `celery` to provide a task queue.

## Other dependencies

- `whitenoise` to serve assets in Python for production. Handles compression and caching headers. [Docs](http://whitenoise.evans.io/en/stable/).
  - Installed as a middleware.

!!! info
    You can get documentation on Models, Views, Templates, etc. by visiting the back-office of your deployment as an admin and clicking "View documentation" in the toolbar.
