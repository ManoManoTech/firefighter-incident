from __future__ import annotations

import pytest

from firefighter.incidents.forms.select_impact import SelectImpactForm


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("form_data", "expected_priority"),
    [
        (
            {
                "set_impact_type_business_impact": "HI",
                "set_impact_type_sellers_impact": "NO",
                "set_impact_type_customers_impact": "NO",
                "set_impact_type_employees_impact": "NO",
            },
            1,
        ),
        (
            {
                "set_impact_type_business_impact": "LO",
                "set_impact_type_sellers_impact": "LO",
                "set_impact_type_customers_impact": "MD",
                "set_impact_type_employees_impact": "NO",
            },
            2,
        ),
        (
            {
                "set_impact_type_business_impact": "LO",
                "set_impact_type_sellers_impact": "LO",
                "set_impact_type_customers_impact": "LO",
                "set_impact_type_employees_impact": "NO",
            },
            3,
        ),
        (
            {
                "set_impact_type_business_impact": "LO",
                "set_impact_type_sellers_impact": "NO",
                "set_impact_type_customers_impact": "NO",
                "set_impact_type_employees_impact": "NO",
            },
            4,
        ),
        (
            {
                "set_impact_type_business_impact": "NO",
                "set_impact_type_sellers_impact": "NO",
                "set_impact_type_customers_impact": "NO",
                "set_impact_type_employees_impact": "NO",
            },
            4,
        ),
    ],
)
def test_suggest_priority_from_impact(form_data, expected_priority):
    form = SelectImpactForm(data=form_data)
    assert form.is_valid()
    priority = form.suggest_priority_from_impact()
    assert priority == expected_priority


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("form_data", "expected_priority"),
    [
        (
            {
                "set_impact_type_business_impact": "INVALID",
                "set_impact_type_sellers_impact": "NO",
                "set_impact_type_customers_impact": "NO",
                "set_impact_type_employees_impact": "NO",
            },
            4,
        ),
        (
            {
                "set_impact_type_business_impact": "LO",
                "set_impact_type_sellers_impact": "INVALID",
                "set_impact_type_customers_impact": "MD",
                "set_impact_type_employees_impact": "NO",
            },
            4,
        ),
        (
            {
                "set_impact_type_business_impact": "LO",
                "set_impact_type_sellers_impact": "LO",
                "set_impact_type_customers_impact": "INVALID",
                "set_impact_type_employees_impact": "NO",
            },
            4,
        ),
    ],
)
@pytest.mark.django_db()
def test_suggest_priority_from_impact_with_invalid_form(form_data, expected_priority):
    form = SelectImpactForm(data=form_data)
    assert not form.is_valid()
    priority = form.suggest_priority_from_impact()
    assert priority == expected_priority
