from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, NotRequired, Required, TypedDict

from django.urls import reverse
from django_components import component


class _Format(TypedDict):
    label: str
    url: str
    fields: str


class Data(TypedDict):
    default_format: Mapping[str, Any]  # _Format
    formats: Sequence[Mapping[str, Any]]  # list[_Format]


Args = tuple[str]


class Kwargs(TypedDict, total=False):
    base_url: Required[str]
    default_fmt: NotRequired[tuple[str, str | None, str | None]]


@component.register("export_button")
class ExportButton(component.Component):
    template_name = "export_button/export_button.html"

    def get_context_data(
        self,
        base_url: str,
        default_fmt: tuple[str, str | None, str | None] | None = None,
        **kwargs: Any,
    ) -> Data:
        default_fmt = default_fmt or ("csv", None, None)
        fmts: list[tuple[str, str | None, str | None]] = [
            ("json", None, None),
            ("tsv", None, None),
            ("csv", "__all__", "(Full)"),
            ("tsv", "__all__", "(Full)"),
        ]

        default_format = self.make_fmt(default_fmt, base_url)
        formats = [self.make_fmt(fmt, base_url) for fmt in fmts]

        return Data(default_format=default_format, formats=formats)

    @staticmethod
    def make_fmt(
        format_: tuple[str, str | None, str | None], base_reverse: str
    ) -> _Format:
        return {
            "label": f"Export {format_[0].upper()}{' ' + format_[2] if format_[2] else ''}",
            "url": f"{reverse(base_reverse, args=[format_[0]])}",
            "fields": format_[1] or "",
        }
