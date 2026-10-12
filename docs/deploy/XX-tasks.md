# Celery tasks

This project uses [Celery](https://docs.celeryproject.org/en/stable/) to run asynchronous tasks.

## Running

You will need to run a Celery worker to run the tasks, and a Celery beat to schedule them.

```bash
pdm run celery-worker
```

```bash
pdm run celery-beat
```

!!! note
    A Django management command is also available to run a specific task:

    ```bash
    pdm run ff-manage task <task_name>
    ```

## Scheduling tasks

Only one task is scheduled by default: `firefighter.celery_heartbeat`, every minute (see [Health checks](#health-checks)). It is declared in the `beat_schedule` Celery setting, which the database scheduler syncs when beat starts.

You can schedule other tasks through the Django admin interface.

## Health checks

Two endpoints report the state of the application:

- `/api/v2/firefighter/monitoring/healthcheck` checks the database only. Use it for the liveness and readiness probes of the web pods.
- `/api/v2/firefighter/monitoring/readiness` checks the database, Redis and Celery, and answers `503` when one of them fails. Each failure is also logged at `ERROR` level.

The Celery check reads the timestamp written by the last `firefighter.celery_heartbeat` run. It fails when that timestamp is missing or older than 5 minutes, which means that beat, the broker or every worker has been down for that long.

!!! note
    The check does not ping the workers. With the gevent pool, a worker stops answering broadcast commands for good once their idle Redis connection is closed (e.g. by a proxy idle timeout), while it keeps consuming tasks: a ping would report a working worker as down.
