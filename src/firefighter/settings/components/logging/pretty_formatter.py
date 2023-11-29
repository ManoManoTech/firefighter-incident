from __future__ import annotations

import logging
from functools import cache
from typing import Final

COLORS: dict[str, str] = {
    "Forest Green": "#086e3f",
    "Emerald Green": "#58ad72",
    "Lint": "#4bd676",
    "Pale Lint": "#75e097",
    "Fuchsia": "#fb4570",
    "Hot Pink": "#fb6b90",
    "Pink": "#fb8da0",
    "Pink White": "#efebe0",
    "Red": "#ed4040",
    "Ivory": "#f1ece4",
    "Nude": "#c3b090",
    "Sand Dollar": "#de943a",
    "Tan": "#92794f",
    "Blue Gray": "#8da7c4",
    "Sky": "#ace1fc",
    "Stone Blue": "#8da7c4",
    "White Blue": "#e5ddfc",
}

PALETTES = {
    logging.DEBUG: ["Blue Gray", "Sky", "Stone Blue", "White Blue"],
    logging.INFO: ["Forest Green", "Lint", "Emerald Green", "Pale Lint"],
    logging.WARNING: ["Nude", "Tan", "Nude", "Sand Dollar"],
    logging.ERROR: ["Hot Pink", "Fuchsia", "Pink", "Red"],
    logging.CRITICAL: ["Hot Pink", "Fuchsia", "Pink", "Red"],
}
# pylint: disable=consider-using-f-string

_ANSI_END: Final[str] = "\x1b[0m"


def _html_to_triple_dec(html_code: str) -> list[int]:
    return [int(x, 16) for x in (html_code[1:3], html_code[3:5], html_code[5:8])]


@cache
def _ansi_fg(name: str) -> str:
    html_code = COLORS[name]
    return "\x1b[38;2;{};{};{}m".format(*_html_to_triple_dec(html_code))


class PrettyFormatter(logging.Formatter):
    """A custom logging formatter that formats log records with colors and a pretty output, for local development.

    Opiniated about what is pretty.

    Attributes:
        _style (logging._STYLES): The logging style used for formatting.
        _fmt (str): The logging format string used for formatting.
    """

    def _set_format(self, fmt: str, style: str = "%") -> None:
        self._style = logging._STYLES[style][0](fmt)  # type: ignore[operator] # noqa: SLF001 # Mysticism 🤔
        self._fmt = self._style._fmt  # noqa: SLF001

    def format(self, record: logging.LogRecord) -> str:
        # Reference attributes: https://docs.python.org/3/library/logging.html#logrecord-attributes
        palette = PALETTES.get(record.levelno, PALETTES[logging.DEBUG])
        self._set_format(
            f"{_ansi_fg(palette[0])}%(asctime)s "
            f"{_ansi_fg(palette[1])}%(levelname)-8s "
            f"{_ansi_fg(palette[2])}%(name)s:%(lineno)d "
            f"{_ansi_fg(palette[3])}%(message)s"
            f"{_ANSI_END}"
        )
        return super().format(record)
