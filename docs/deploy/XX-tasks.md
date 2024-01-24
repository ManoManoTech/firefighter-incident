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

By default, no tasks are scheduled.

You can schedule tasks through the Django admin interface.
