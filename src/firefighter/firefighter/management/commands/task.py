from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.core.management.base import BaseCommand, CommandError, CommandParser

from firefighter.firefighter.celery_client import app as celery_app

if TYPE_CHECKING:
    from celery.app.task import Task

    Task.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore[attr-defined]


class Command(BaseCommand):
    help = "Run a celery task from the command line."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("task_name", type=str, choices=celery_app.tasks.keys())

    def handle(self, *args: Any, **options: Any) -> None:
        tasks: dict[str, Task[Any, Any]] = cast(
            "dict[str, Task[Any, Any]]", celery_app.tasks
        )
        task_name = options["task_name"]

        if task_name in tasks:
            self.stdout.write(self.style.SUCCESS(f"Running task {task_name}"))
            task: Task[Any, Any] = tasks[task_name]
            task()
            self.stdout.write(self.style.SUCCESS(f"Successfully ran task {task_name}"))
        else:
            sep = "\n - "
            err_msg = f'Task "{task_name}" does not exist. Available tasks are:\n - {sep.join(sorted(tasks))}'
            raise CommandError(err_msg)
