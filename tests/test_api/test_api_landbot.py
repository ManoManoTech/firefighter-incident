from __future__ import annotations

import pytest
from rest_framework.exceptions import ValidationError

from firefighter.raid.serializers import (
    IgnoreEmptyStringListField,
    LandbotIssueRequestSerializer,
)

base_valid_data = {
    "summary": "Test summary",
    "description": "Test description",
    "seller_contract_id": "123456",
    "zoho": "https://test_url.com",
    "platform": "FR",
    "reporter_email": "test_email@example.com",
    "incident_category": "Test Area",
    "suggested_team_routing": "TSTPRJ",
    "labels": ["testLabel1", "testLabel2"],
    "environments": ["PRD"],
    "issue_type": "Incident",
    "business_impact": "High",
    "priority": 1,
    "attachments": "['https://test-attachment.com/test1','https://test-attachment2.com/test2',]",
}


def test_valid_data() -> None:
    # Given
    valid_data = base_valid_data
    serializer = LandbotIssueRequestSerializer(data=valid_data)

    # When & Then
    assert serializer.is_valid()


def test_valid_data_no_attachments() -> None:
    # Given
    valid_data = base_valid_data
    valid_data["attachments"] = ""
    serializer = LandbotIssueRequestSerializer(data=valid_data)

    # When & Then
    assert serializer.is_valid()
    assert len(serializer.validated_data["attachments"]) == 0


def test_valid_data_no_labels() -> None:
    # Given
    valid_data = {
        **base_valid_data,
        "labels": [],  # no labels
    }
    serializer = LandbotIssueRequestSerializer(data=valid_data)

    # When & Then
    assert serializer.is_valid()


def test_valid_data_no_environments() -> None:
    # Given
    valid_data = {
        **base_valid_data,
        "environments": ["-"],  # no environments
    }
    serializer = LandbotIssueRequestSerializer(data=valid_data)

    # When & Then
    assert serializer.is_valid()
    assert serializer.validated_data["environments"] == ["-"]


def test_invalid_data_label_with_space() -> None:
    # Given
    invalid_data = {
        **base_valid_data,
        "labels": ["test label"],  # label with space
    }
    serializer = LandbotIssueRequestSerializer(data=invalid_data)

    # When & Then
    assert not serializer.is_valid()
    assert "labels" in serializer.errors


def test_invalid_data_label_too_long() -> None:
    # Given
    invalid_data = {
        **base_valid_data,
        "labels": ["ab" * 129],  # label too long
    }
    serializer = LandbotIssueRequestSerializer(data=invalid_data)

    # When & Then
    assert not serializer.is_valid()
    assert "labels" in serializer.errors


def test_ignore_empty_string_list_field() -> None:
    serializer_field = IgnoreEmptyStringListField()

    # Test with no empty strings
    input_data = ["test1", "test2", "test3"]
    output_data = serializer_field.to_internal_value(input_data)
    assert output_data == input_data, "Should return the same list if no empty strings"

    # Test with some empty strings
    input_data = ["test1", "", "test3", ""]
    expected_output_data = ["test1", "test3"]
    output_data = serializer_field.to_internal_value(input_data)
    assert output_data == expected_output_data, "Should ignore empty strings"

    # Test with only empty strings
    input_data = ["", "", ""]
    expected_output_data = []
    output_data = serializer_field.to_internal_value(input_data)
    assert (
        output_data == expected_output_data
    ), "Should return empty list if all strings are empty"

    # Test with non-list input
    input_data_str = "test"
    with pytest.raises(ValidationError):
        serializer_field.to_internal_value(input_data_str)
