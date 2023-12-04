from __future__ import annotations

import os
from typing import Any

import gunicorn.app.wsgiapp
from gunicorn.app.base import Application

HTTP_BIND = os.getenv("HTTP_BIND", "0.0.0.0")  # noqa: S104
HTTP_PORT = int(os.getenv("HTTP_PORT", "8000"))


class StandaloneApplication(gunicorn.app.wsgiapp.WSGIApplication):
    def __init__(self, app: str, options: dict[str, Any]) -> None:  # noqa: ARG002
        self.options = options
        self.app_uri = "firefighter.firefighter.wsgi"
        super().__init__()

    def load_config(self) -> None:
        Application.load_config(self)
        if self.cfg is None:
            raise ValueError("cfg is None")
        self.cfg.set("workers", int(os.getenv("GUNICORN_WORKERS", "8")))
        self.cfg.set("bind", f"{HTTP_BIND}:{HTTP_PORT}")

        if "GUNICORN_TIMEOUT" in os.environ:
            self.cfg.set("timeout", int(os.environ["GUNICORN_TIMEOUT"]))
        self.app_uri = "firefighter.firefighter.wsgi"


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firefighter.firefighter.settings")
    # ruff: noqa: PLC0415
    from django import setup

    setup()
    from django.core.management import call_command

    call_command("migrate")
    call_command("collectstatic", "--no-input")

    StandaloneApplication(
        "%(prog)s [OPTIONS] [APP_MODULE]",
        {
            "bind": f"{HTTP_BIND}:{HTTP_PORT}",  # noqa: S104
            "workers": 4,
            "wsgi_app": "firefighter.firefighter.wsgi",
        },
    ).run()


if __name__ == "__main__":
    main()
