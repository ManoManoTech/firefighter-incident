from __future__ import annotations

BASE_TABLE_ATTRS: dict[str, dict[str, str] | str] = {
    "class": "table-auto divide-y divide-neutral-200 dark:divide-neutral-600 w-full rounded-md",
    "th": {
        "class": "px-2 py-3 tracking-wider hover:underline uppercase text-xs font-medium  whitespace-nowrap",
        "scope": "col",
    },
    "td": {"class": "px-3 py-4 whitespace-nowrap  text-center"},
    "thead": {
        "class": "bg-neutral-50 dark:bg-neutral-700  text-neutral-500 dark:text-neutral-50 rounded-t-md",
        "scope": "col",
    },
    "tbody": {
        "class": "bg-base-100 dark:bg-neutral-800 divide-y divide-neutral-200 text-base-content dark:divide-neutral-600 text-sm font-medium"
    },
}
# XXX HTMX support for pagination/django-tables2 ordering
# XXX Reuse more columns and styles!
