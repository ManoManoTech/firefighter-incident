from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.management.base import (
    BaseCommand,
    CommandError,
    CommandParser,
    OutputWrapper,
)

if TYPE_CHECKING:
    from celery.app.task import Task

    Task.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore[attr-defined]


class Command(BaseCommand):
    help = "Generate the Slack App Manifest from your settings."
    requires_migrations_checks = False
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        output_format = parser.add_mutually_exclusive_group(required=True)
        output_format.add_argument(
            "--json",
            action="store_const",
            dest="output_format",
            const="json",
            help="Output the manifest as JSON.",
            default="json",
        )
        output_format.add_argument(
            "--yml",
            "--yaml",
            action="store_const",
            dest="output_format",
            const="yml",
            help="Output the manifest as YAML.",
        )
        # Add --public-url option for tunneling
        parser.add_argument(
            "--public-url",
            action="store",
            dest="public_url",
            help="The public URL to use for the manifest If not provided, BASE_URL will be used.",
            required=False,
        )

    def handle(self, *args: Any, **options: Any) -> None:
        output_format = options["output_format"]
        if output_format is None:
            raise CommandError("You must specify an output format (--json or --yml).")
        if output_format not in {"json", "yml"}:
            msg = f"Invalid output format: {output_format}. Must be either json or yml."
            raise CommandError(msg)

        base_url: str = settings.BASE_URL
        if not base_url:
            raise CommandError("You must specify a BASE_URL in your settings.")
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"
        app_display_name = settings.APP_DISPLAY_NAME

        public_base_url = (options.get("public_url") or base_url).rstrip("/")
        main_command: str = settings.SLACK_INCIDENT_COMMAND
        command_aliases: list[str] = settings.SLACK_INCIDENT_COMMAND_ALIASES
        if not main_command.startswith("/"):
            main_command = f"/{main_command}"
        if command_aliases:
            command_aliases = [
                f"/{alias}" if not alias.startswith("/") else alias
                for alias in command_aliases
            ]
            command_aliases = [
                alias for alias in command_aliases if alias != main_command
            ]

        manifest = get_manifest(
            app_display_name, main_command, command_aliases, public_base_url
        )
        output_manifest(manifest, output_format, self.stdout)


def get_manifest(
    app_display_name: str,
    main_command: str,
    command_aliases: list[str],
    public_base_url: str,
) -> dict[str, Any]:
    return {
        "display_information": {
            "name": app_display_name[:35],
            "description": "Incident Management Bot",
            "background_color": "#000000",
        },
        "features": {
            "app_home": {
                "home_tab_enabled": True,
                "messages_tab_enabled": False,
                "messages_tab_read_only_enabled": False,
            },
            "bot_user": {
                "display_name": app_display_name[:35],
                "always_online": True,
            },
            "shortcuts": [
                {
                    "name": "Open incident",
                    "type": "global",
                    "callback_id": "open_incident",
                    "description": "Open an incident and get help",
                }
            ],
            "slash_commands": [
                {
                    "command": command,
                    "url": f"{public_base_url}/api/v2/firefighter/slack/incident/",
                    "description": "Manage Incidents 🚨",
                    "usage_hint": "[open|update|close|status|help]",
                    "should_escape": False,
                }
                for command in [main_command, *command_aliases]
            ],
        },
        "oauth_config": {
            "scopes": {
                "bot": [
                    "bookmarks:read",
                    "bookmarks:write",
                    "channels:history",
                    "channels:join",
                    "channels:manage",
                    "channels:read",
                    "chat:write",
                    "chat:write.customize",
                    "chat:write.public",
                    "commands",
                    "groups:history",
                    "groups:read",
                    "groups:write",
                    "im:read",
                    "im:write",
                    "mpim:read",
                    "mpim:write",
                    "pins:read",
                    "pins:write",
                    "reactions:read",
                    "usergroups:read",
                    "usergroups:write",
                    "users.profile:read",
                    "users:read",
                    "users:read.email",
                    "metadata.message:read",
                    "team:read",
                    "incoming-webhook",
                ]
            }
        },
        "settings": {
            "event_subscriptions": {
                "request_url": f"{public_base_url}/api/v2/firefighter/slack/incident/",
                "bot_events": [
                    "app_home_opened",
                    "channel_archive",
                    "channel_deleted",
                    "channel_id_changed",
                    "channel_rename",
                    "channel_unarchive",
                    "group_archive",
                    "group_rename",
                    "group_unarchive",
                    "message.channels",
                    "message.groups",
                    "reaction_added",
                ],
            },
            "interactivity": {
                "is_enabled": True,
                "request_url": f"{public_base_url}/api/v2/firefighter/slack/incident/",
            },
            "org_deploy_enabled": False,
            "socket_mode_enabled": False,
            "token_rotation_enabled": False,
        },
    }


def output_manifest(
    manifest: dict[str, Any], output_format: str, stdout: OutputWrapper
) -> None:
    if output_format == "json":
        import json  # noqa: PLC0415

        stdout.write(json.dumps(manifest, indent=2, ensure_ascii=False))

    elif output_format == "yml":
        import yaml  # noqa: PLC0415

        stdout.write(yaml.dump(manifest, allow_unicode=True))
