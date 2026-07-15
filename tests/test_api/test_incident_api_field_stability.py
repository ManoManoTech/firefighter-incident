"""Stability contract for the incidents API export fields.

The incidents endpoint advertises a documented set of (dot-nested) export fields, rendered
as CSV/TSV columns or JSON keys. Those field paths are a public API contract: renaming or
removing one is a BREAKING change for downstream consumers, which receive an empty column
rather than an error. This test pins the contract so such a change fails the build and must
be made deliberately (bump the API version, update the CHANGELOG, coordinate consumers)
rather than slipping through unnoticed.

Update the constants below only as an intentional, documented API change.
"""

from __future__ import annotations

from firefighter.api.serializers import IncidentSerializer

# Top-level export fields that must remain available on the incidents serializer.
STABLE_TOP_LEVEL = (
    "id",
    "ignore",
    "status",
    "title",
    "description",
    "created_at",
    "slack_channel_name",
    "status_page_url",
)

# Nested object fields: parent -> required leaf attributes.
STABLE_NESTED = {
    "environment": ("value",),
    "priority": ("name",),
    "incident_category": ("name", "group"),
}

# Grouped one-to-many maps (keyed by a dynamic slug/name): parent -> required child leaves.
STABLE_GROUP_CHILD_LEAVES = {
    "roles": ("name", "email"),
    "costs": ("amount",),
    "metrics": ("duration_seconds",),
}


def _incident_fields() -> dict:
    return IncidentSerializer().fields


def test_incident_api_exposes_stable_top_level_fields() -> None:
    fields = _incident_fields()
    expected = (*STABLE_TOP_LEVEL, *STABLE_NESTED, *STABLE_GROUP_CHILD_LEAVES)
    missing = [name for name in expected if name not in fields]
    assert not missing, f"BREAKING: incidents API no longer exposes: {missing}"


def test_incident_api_exposes_stable_nested_leaves() -> None:
    fields = _incident_fields()
    for parent, leaves in STABLE_NESTED.items():
        child_fields = fields[parent].fields
        missing = [leaf for leaf in leaves if leaf not in child_fields]
        assert not missing, f"BREAKING: incidents API '{parent}.*' changed: {missing}"
    group_fields = fields["incident_category"].fields["group"].fields
    assert "name" in group_fields, "BREAKING: 'incident_category.group.name' changed"


def test_incident_api_exposes_stable_grouped_child_leaves() -> None:
    fields = _incident_fields()
    for parent, leaves in STABLE_GROUP_CHILD_LEAVES.items():
        child_fields = fields[parent].child_serializer().fields
        missing = [leaf for leaf in leaves if leaf not in child_fields]
        assert not missing, f"BREAKING: incidents API '{parent}.*' changed: {missing}"
