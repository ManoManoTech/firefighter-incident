"""Column-order contract for the stable incident export.

`test_incident_api_field_stability` pins which fields *exist*. It does not pin their
*position*, and position is equally part of the contract: consumers load the CSV into
Snowflake, which maps columns positionally ($1..$N), not by header name.

That gap is how `incident_category.enabled_create`, `jira_ticket_key` and
`jira_ticket_url` broke a downstream consumer — each sorted into the middle of the
alphabetical `?fields=__all__` output and shifted every column after it.

`EXTENDED_EXPORT_FIELDS` exists so that export has a frozen order. These tests fail if
anyone inserts, removes or reorders an entry in the stable block, or appends a new field
anywhere other than the end.
"""

from __future__ import annotations

from firefighter.api.renderer import CSVRenderer
from firefighter.api.views.incidents import EXTENDED_EXPORT_FIELDS

# The order frozen as of firefighter-incident 0.0.65, before the three fields below were
# added. Consumers map these positionally — a change here is a BREAKING change.
STABLE_PREFIX = (
    "costs.Business Volume lost.amount",
    "costs.Business Volume lost.details",
    "costs.Infrastructure cost.amount",
    "costs.Infrastructure cost.details",
    "costs.Revenue lost.amount",
    "costs.Revenue lost.details",
    "created_at",
    "created_by.email",
    "created_by.id",
    "created_by.name",
    "description",
)

# Fields added after the freeze. New fields belong at the END, never inserted.
APPENDED_TAIL = (
    "incident_category.enabled_create",
    "jira_ticket_key",
    "jira_ticket_url",
)


def test_stable_prefix_is_unchanged() -> None:
    """The first columns must never move — they anchor every positional mapping."""
    actual = EXTENDED_EXPORT_FIELDS[: len(STABLE_PREFIX)]
    assert actual == STABLE_PREFIX, (
        "BREAKING: the stable export column prefix changed. Downstream consumers map "
        "columns by position; inserting or reordering shifts all following columns. "
        "New fields must be appended at the END of EXTENDED_EXPORT_FIELDS."
    )


def test_new_fields_are_appended_at_the_end() -> None:
    """Fields added after the freeze sit at the tail, in the order they were added."""
    assert EXTENDED_EXPORT_FIELDS[-len(APPENDED_TAIL) :] == APPENDED_TAIL, (
        "BREAKING: post-freeze fields are no longer the final columns. Append new "
        "fields at the END of EXTENDED_EXPORT_FIELDS, never in alphabetical position."
    )


def test_no_duplicate_columns() -> None:
    dupes = {f for f in EXTENDED_EXPORT_FIELDS if EXTENDED_EXPORT_FIELDS.count(f) > 1}
    assert not dupes, f"duplicate export columns: {sorted(dupes)}"


def test_presets_pass_the_pinned_field_list() -> None:
    """The dropdown presets must send the explicit list, not `__all__`.

    Imported inside the test on purpose: importing `incidents.views.views` at module
    level pulls the view layer in at collection time, which perturbs an order-fragile
    Slack test elsewhere in the suite.
    """
    from firefighter.incidents.views.views import incident_export_presets

    presets = incident_export_presets()
    assert presets, "no export presets configured"
    expected = ",".join(EXTENDED_EXPORT_FIELDS)
    for fmt, fields, label in presets:
        assert fields == expected, f"preset {label!r} ({fmt}) does not pin the columns"
        assert fields != "__all__", f"preset {label!r} still uses __all__"


def test_renderer_emits_the_pinned_order_verbatim() -> None:
    """The property the whole approach rests on: an explicit header is emitted as given.

    `CSVRenderer._get_headers` short-circuits for a wildcard-free header, so the column
    order is exactly what we pass in — never sorted.

    Deliberately DB-free: building a real incident fires creation signals that leak into
    unrelated Slack tests later in the suite. Field *presence* on the serializer is
    already covered by `test_incident_api_field_stability`; this test is about the
    renderer, so synthetic rows are both sufficient and side-effect free.
    """
    header = list(EXTENDED_EXPORT_FIELDS)
    data = [dict.fromkeys(header, "x")]

    rows = list(CSVRenderer().tablize(data, header=header, labels=None))

    assert rows[0] == header, "renderer reordered an explicit header"
    assert rows[0] != sorted(header), (
        "the pinned order equals alphabetical order, so this test could not detect a "
        "regression to sorting — the appended tail must not be alphabetically last"
    )
    assert len(rows[1]) == len(header), "row width does not match the header"
