# tests/test_fields.py
from __future__ import annotations

import pytest
from django.forms import Form

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.forms.utils import EnumChoiceField, GroupedModelChoiceField
from firefighter.incidents.models.component import Component
from firefighter.incidents.models.group import Group


class EnumChoiceFieldForm(Form):
    status = EnumChoiceField(enum_class=IncidentStatus)


class GroupedModelChoiceFieldForm(Form):
    component = GroupedModelChoiceField(
        choices_groupby="group", queryset=Component.objects.all()
    )


@pytest.fixture
def group() -> Group:
    return Group.objects.create(name="Group 1")


@pytest.fixture
def components(group: Group):
    return [
        Component.objects.create(name="Issue category 1", group=group, order=1),
        Component.objects.create(name="Issue category 2", group=group, order=2),
    ]


def test_enum_choice_field_valid() -> None:
    form = EnumChoiceFieldForm({"status": IncidentStatus.OPEN})

    assert form.is_valid()
    assert form.cleaned_data["status"] == IncidentStatus.OPEN


def test_enum_choice_field_invalid() -> None:
    form = EnumChoiceFieldForm({"status": 999})
    assert not form.is_valid()
    assert "status" in form.errors


@pytest.mark.django_db
def test_grouped_model_choice_field_valid(components: list[Component]):
    form = GroupedModelChoiceFieldForm({"component": components[0].id})
    assert form.is_valid()
    assert form.cleaned_data["component"] == components[0]


def test_grouped_model_choice_field_invalid() -> None:
    form = GroupedModelChoiceFieldForm({"component": "non-existent-id"})
    assert not form.is_valid()
    assert "component" in form.errors


@pytest.fixture(scope="module")
def test_grouped_model_choice_field_grouping(
    components: list[Component],
):
    form = GroupedModelChoiceFieldForm()
    grouped_choices = list(
        form.fields["component"].iterator(field=form.fields["component"])
    )
    assert len(grouped_choices) == 2  # One for the empty choice, and one for the group
    assert grouped_choices[0] == ("", form.fields["component"].empty_label)
    assert grouped_choices[1][0] == components[0].group
    assert len(grouped_choices[1][1]) == 2  # Two components in the group
