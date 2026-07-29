"""Tests for `IncidentCategory.enabled_create`.

A retired category must disappear from the *create* pickers while staying
selectable everywhere an existing incident is edited — otherwise an incident
already filed against it could not be updated or closed, because its own
category would be missing from the choice list.
"""

from __future__ import annotations

import pytest

from firefighter.incidents.factories import IncidentCategoryFactory
from firefighter.incidents.forms.close_incident import CloseIncidentForm
from firefighter.incidents.forms.create_incident import CreateIncidentForm
from firefighter.incidents.forms.unified_incident import UnifiedIncidentForm
from firefighter.incidents.forms.update_status import UpdateStatusForm
from firefighter.incidents.models.incident_category import IncidentCategory


def _category_choices(form: object, field_name: str = "incident_category") -> list:
    """Return the IncidentCategory objects offered by a form field."""
    return list(form.fields[field_name].queryset)


@pytest.fixture
def enabled_category(db) -> IncidentCategory:
    return IncidentCategoryFactory(name="Foundations", enabled_create=True)


@pytest.fixture
def retired_category(db) -> IncidentCategory:
    return IncidentCategoryFactory(name="Web performance", enabled_create=False)


@pytest.mark.django_db
class TestEnabledCreateDefault:
    def test_defaults_to_true(self) -> None:
        """Existing categories keep working: the field backfills to True."""
        category = IncidentCategoryFactory()

        assert category.enabled_create is True


@pytest.mark.django_db
class TestCreateFormsHideRetiredCategories:
    def test_unified_form_excludes_retired_category(
        self, enabled_category: IncidentCategory, retired_category: IncidentCategory
    ) -> None:
        choices = _category_choices(UnifiedIncidentForm())

        assert enabled_category in choices
        assert retired_category not in choices

    def test_web_create_form_excludes_retired_category(
        self, enabled_category: IncidentCategory, retired_category: IncidentCategory
    ) -> None:
        """`CreateIncidentForm` (web UI, `IncidentCreateView`) is a *sibling* of
        `UnifiedIncidentForm`, not its parent — both declare the field on their own,
        so filtering only one would leave a hole.
        """
        choices = _category_choices(CreateIncidentForm())

        assert enabled_category in choices
        assert retired_category not in choices

    def test_slack_modal_form_inherits_the_filter(
        self, enabled_category: IncidentCategory, retired_category: IncidentCategory
    ) -> None:
        """The Slack opening modal subclasses `UnifiedIncidentForm`."""
        pytest.importorskip("firefighter.slack")
        from firefighter.slack.views.modals.opening.details.unified import (
            UnifiedIncidentFormSlack,
        )

        choices = _category_choices(UnifiedIncidentFormSlack())

        assert enabled_category in choices
        assert retired_category not in choices


@pytest.mark.django_db
class TestRetiredCategoryRejectedOnSubmit:
    """Hiding a category from the rendered choices is not enough — a stale Slack
    modal or a replayed payload can still post its UUID.
    """

    def test_unified_form_rejects_retired_category_on_submit(
        self, retired_category: IncidentCategory
    ) -> None:
        form = UnifiedIncidentForm(
            data={
                "title": "Something is broken",
                "description": "A description long enough to pass validation.",
                "incident_category": str(retired_category.id),
            }
        )
        form.is_valid()

        assert "incident_category" in form.errors

    def test_web_create_form_rejects_retired_category_on_submit(
        self, retired_category: IncidentCategory
    ) -> None:
        form = CreateIncidentForm(
            data={
                "title": "Something is broken",
                "description": "A description long enough to pass validation.",
                "incident_category": str(retired_category.id),
            }
        )
        form.is_valid()

        assert "incident_category" in form.errors


@pytest.mark.django_db
class TestEditFormsKeepRetiredCategories:
    """Regression guard: filtering these would break incidents already filed
    against a retired category.
    """

    def test_update_status_form_keeps_retired_category(
        self, enabled_category: IncidentCategory, retired_category: IncidentCategory
    ) -> None:
        choices = _category_choices(UpdateStatusForm())

        assert enabled_category in choices
        assert retired_category in choices

    def test_close_form_keeps_retired_category(
        self, enabled_category: IncidentCategory, retired_category: IncidentCategory
    ) -> None:
        choices = _category_choices(CloseIncidentForm())

        assert enabled_category in choices
        assert retired_category in choices

    def test_retired_category_still_validates_on_update(
        self, retired_category: IncidentCategory
    ) -> None:
        """An incident on a retired category can still be saved through the
        update-status form.
        """
        form = UpdateStatusForm(
            data={
                "message": "Still working on it.",
                "status": "FIXED",
                "priority": "",
                "incident_category": str(retired_category.id),
            }
        )
        form.is_valid()

        assert "incident_category" not in form.errors


@pytest.mark.django_db
class TestListingsAreUnaffected:
    def test_retired_category_still_queryable(
        self, retired_category: IncidentCategory
    ) -> None:
        """History, API and filters must keep seeing retired categories."""
        assert retired_category in IncidentCategory.objects.all()
