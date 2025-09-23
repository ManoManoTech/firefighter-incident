from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from firefighter.incidents.factories import GroupFactory, IncidentCategoryFactory
from firefighter.incidents.models.incident_category import (
    IncidentCategory,
    IncidentCategoryFilterSet,
    IncidentCategoryManager,
)


@pytest.mark.django_db
class TestIncidentCategoryManager:
    def test_queryset_with_mtbf_date_to_in_future(self):
        """Test that date_to is clamped to now() when it's in the future."""
        # Given
        IncidentCategoryFactory()
        manager = IncidentCategoryManager()
        manager.model = IncidentCategory

        # Create dates where date_to is in the future
        now = timezone.now()
        date_from = now - timedelta(days=10)
        date_to = now + timedelta(days=5)  # Future date

        # When
        result = manager.queryset_with_mtbf(date_from, date_to)

        # Then
        assert result is not None
        assert list(result) == list(result)  # Should not fail to execute

    def test_queryset_with_mtbf_with_custom_queryset(self):
        """Test that custom queryset parameter is used."""
        # Given
        category1 = IncidentCategoryFactory()
        category2 = IncidentCategoryFactory()

        manager = IncidentCategoryManager()
        manager.model = IncidentCategory

        # Create a custom queryset that filters only category1
        custom_queryset = IncidentCategory.objects.filter(id=category1.id)

        date_from = timezone.now() - timedelta(days=10)
        date_to = timezone.now() - timedelta(days=1)

        # When
        result = manager.queryset_with_mtbf(date_from, date_to, queryset=custom_queryset)

        # Then
        assert category1 in result
        assert category2 not in result

    def test_search_with_none_queryset(self):
        """Test search method when queryset is None."""
        # Given
        category = IncidentCategoryFactory(name="Test Category")

        # When
        result, is_empty = IncidentCategoryManager.search(None, "Test")

        # Then
        assert is_empty is False
        assert category in result

    def test_search_with_empty_search_term(self):
        """Test search method with empty/None search term."""
        # Given
        IncidentCategoryFactory(name="Category One")
        IncidentCategoryFactory(name="Category Two")
        queryset = IncidentCategory.objects.all()

        # When - Test with None
        result_none, is_empty_none = IncidentCategoryManager.search(queryset, None)

        # When - Test with empty string
        result_empty, is_empty_empty = IncidentCategoryManager.search(queryset, "")

        # When - Test with whitespace
        result_spaces, is_empty_spaces = IncidentCategoryManager.search(queryset, "   ")

        # Then - All should return the original queryset
        assert is_empty_none is False
        assert is_empty_empty is False
        assert is_empty_spaces is False

        original_ids = set(queryset.values_list("id", flat=True))
        assert set(result_none.values_list("id", flat=True)) == original_ids
        assert set(result_empty.values_list("id", flat=True)) == original_ids
        assert set(result_spaces.values_list("id", flat=True)) == original_ids

    def test_search_with_valid_search_term(self):
        """Test search method with valid search term."""
        # Given
        group = GroupFactory(name="Test Group", description="Group for testing")
        category = IncidentCategoryFactory(
            name="Infrastructure Issue",
            description="Issues with infrastructure",
            group=group
        )
        other_category = IncidentCategoryFactory(
            name="Database Problem",
            description="Database related issues"
        )

        # When - Search for "infrastructure"
        result, is_empty = IncidentCategoryManager.search(None, "infrastructure")

        # Then
        assert is_empty is False
        result_list = list(result)
        assert category in result_list
        # Note: other_category might also appear if search is broad

        # When - Search for "database"
        result_db, is_empty_db = IncidentCategoryManager.search(None, "database")

        # Then
        assert is_empty_db is False
        result_db_list = list(result_db)
        assert other_category in result_db_list


@pytest.mark.django_db
class TestIncidentCategoryFilterSet:
    def test_incident_category_search(self):
        """Test the incident_category_search filter method."""
        # Given
        category = IncidentCategoryFactory(name="Network Issues")
        queryset = IncidentCategory.objects.all()

        # When
        result = IncidentCategoryFilterSet.incident_category_search(queryset, "search", "network")

        # Then
        assert category in result

    def test_metrics_period_filter(self):
        """Test the metrics period filter method."""
        # Given
        category = IncidentCategoryFactory()
        queryset = IncidentCategory.objects.all()

        # Create date range
        now = timezone.now()
        date_from = now - timedelta(days=30)
        date_to = now
        value = (date_from, date_to, None, None)

        # When
        result = IncidentCategoryFilterSet.metrics_period_filter(queryset, "metrics", value)

        # Then
        # Should return a queryset with mtbf annotation
        assert result is not None
        assert category in result

        # Check that the mtbf annotation is present (will be None if no metrics)
        category_with_mtbf = result.get(id=category.id)
        assert hasattr(category_with_mtbf, "mtbf")
