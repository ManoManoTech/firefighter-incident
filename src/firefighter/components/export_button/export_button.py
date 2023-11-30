from __future__ import annotations

from typing import Any

from django.urls import reverse
from django_components import component


@component.register("export_button")
class ExportButton(component.Component):
    template_name = "export_button/export_button.html"

    def get_context_data(
        self,
        base_url: str,
        *args: Any,
        default_fmt: tuple[str, str | None, str | None] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        default_fmt = default_fmt or ("csv", None, None)
        fmts: list[tuple[str, str | None, str | None]] = [
            ("json", None, None),
            ("tsv", None, None),
            ("csv", "__all__", "(Full)"),
            ("tsv", "__all__", "(Full)"),
        ]

        default_format = self.make_fmt(default_fmt, base_url)
        formats = [self.make_fmt(fmt, base_url) for fmt in fmts]

        return {"default_format": default_format, "formats": formats}

    @staticmethod
    def make_fmt(
        format_: tuple[str, str | None, str | None], base_reverse: str
    ) -> dict[str, str]:
        return {
            "label": f"Export {format_[0].upper()}{' ' + format_[2] if format_[2] else ''}",
            "url": f"{reverse(base_reverse, args=[format_[0]])}",
            "fields": format_[1] or "",
        }
