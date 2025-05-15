from __future__ import annotations

import logging
import re
from functools import cache
from typing import TYPE_CHECKING, Any

from rest_framework_csv.renderers import CSVRenderer as BaseCSVRenderer

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

logger = logging.getLogger(__name__)


class CSVRenderer(BaseCSVRenderer):
    """Renderer which serializes to CSV
    Override the default CSV Renderer to allow hiding header fields.
    Hide head by setting labels to "__hidden__".
    """

    def tablize(
        self, data: Any, header: Any | None = None, labels: Any | None = None
    ) -> Generator[list[Any], None, None]:
        """Convert a list of data into a table.

        If there is a header provided to tablize it will efficiently yield each
        row as needed. If no header is provided, tablize will need to process
        each row in the data in order to construct a complete header. Thus, if
        you have a lot of data and want to stream it, you should probably
        provide a header to the renderer (using the `header` attribute, or via
        the `renderer_context`).
        """
        # Try to pull the header off of the data, if it's not passed in as an
        # argument.
        if not header and hasattr(data, "header"):
            header = data.header

        if data:
            # First, flatten the data (i.e., convert it to a list of
            # dictionaries that are each exactly one level deep).  The key for
            # each item designates the name of the column that the item will
            # fall into.
            data = self.flatten_data(data)

            # Get the set of all unique headers, and sort them (unless already provided).
            data, header = self._get_headers(data, header)

            # Return your "table", with the headers as the first row.
            if labels != "__hidden__":
                if labels:
                    yield [labels.get(x, x) for x in header]
                else:
                    yield header

            # Create a row for each dictionary, filling in columns for which the
            # item has no data with None values.
            for item in data:
                row = [item.get(key, None) for key in header]
                yield row

        elif header:
            # If there's no data but a header was supplied, yield the header.
            if labels:
                yield [labels.get(x, x) for x in header]
            else:
                yield header

        else:
            # Generator will yield nothing if there's no data and no header
            pass

    def _get_headers(
        self, data: Iterable[Any], header: list[str] | None
    ) -> tuple[Iterable[Any], list[str]]:
        # If we already have a header, and it does not contain any wildcards,
        # we can use it as-is.
        has_wildcards = any(".*." in x for x in header) if header else False
        if header and not has_wildcards:
            return data, header

        # We have to materialize the data in order to get the headers.
        data = tuple(data)
        header_fields: set[str] = set()
        for item in data:
            header_fields.update(list(item.keys()))

        if not has_wildcards:
            return data, sorted(header_fields)
        if header is None:
            header = sorted(header_fields)

        to_expand: list[str] = [x for x in header if ".*." in x]
        expanded_headers: dict[str, list[str]] = {
            key: sorted([x for x in header_fields if self._get_regex(key).match(x)])
            for key in to_expand
        }

        return data, [x for h in header for x in expanded_headers.get(h, [h])]

    @staticmethod
    @cache
    def _get_regex(header: str) -> re.Pattern[str]:
        regex = header.replace(".*.", ".+")
        return re.compile(f"^{regex}$")


class TSVRenderer(CSVRenderer):
    """Renderer which serializes to TSV."""

    media_type = "text/tab-separated-values"
    format = "tsv"
    writer_opts = {
        "dialect": "excel-tab",
    }
