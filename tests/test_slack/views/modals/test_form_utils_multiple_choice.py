"""Tests for form_utils.py support of multiple choice fields."""
from __future__ import annotations

import pytest
from django import forms

from firefighter.incidents.models import Environment
from firefighter.slack.views.modals.base_modal.form_utils import (
    SlackForm,
    slack_view_submission_to_dict,
)


@pytest.mark.django_db
class TestMultipleChoiceFields:
    """Test that SlackForm correctly handles ModelMultipleChoiceField and MultipleChoiceField."""

    def test_model_multiple_choice_field_with_initial_list(self, environment_factory):
        """Test ModelMultipleChoiceField with list of model instances as initial."""
        class TestForm(forms.Form):
            environments = forms.ModelMultipleChoiceField(
                queryset=Environment.objects.all(),
                required=True,
            )

        # Create test environments
        env1 = environment_factory(value="PRD", default=True)
        env2 = environment_factory(value="STG", default=True)
        default_envs = [env1, env2]

        slack_form = SlackForm(TestForm)(initial={"environments": default_envs})
        blocks = slack_form.slack_blocks()

        # Should generate blocks without errors
        assert len(blocks) > 0

        # Find the environment block
        env_block = next(b for b in blocks if b.block_id == "environments")
        assert env_block is not None

        # Check it's a multi-select element
        assert env_block.element.type == "multi_static_select"

        # Check initial options
        if default_envs:
            assert len(env_block.element.initial_options) == len(default_envs)

    def test_model_multiple_choice_field_with_callable_initial(self, environment_factory):
        """Test ModelMultipleChoiceField with callable returning list."""
        # Create test environments
        environment_factory(value="PRD", default=True)
        environment_factory(value="STG", default=True)

        def get_default_envs():
            return list(Environment.objects.filter(default=True))

        class TestForm(forms.Form):
            environments = forms.ModelMultipleChoiceField(
                queryset=Environment.objects.all(),
                initial=get_default_envs,
                required=True,
            )

        slack_form = SlackForm(TestForm)()
        blocks = slack_form.slack_blocks()

        # Should generate blocks without errors
        assert len(blocks) > 0

    def test_multiple_choice_field_with_initial_list(self):
        """Test MultipleChoiceField with list of values as initial."""

        class TestForm(forms.Form):
            platforms = forms.MultipleChoiceField(
                choices=[
                    ("FR", "France"),
                    ("DE", "Germany"),
                    ("UK", "United Kingdom"),
                ],
                initial=["FR", "UK"],
                required=True,
            )

        slack_form = SlackForm(TestForm)()
        blocks = slack_form.slack_blocks()

        # Should generate blocks without errors
        assert len(blocks) > 0

        # Find the platforms block
        platform_block = next(b for b in blocks if b.block_id == "platforms")
        assert platform_block is not None

        # Check it's a multi-select element
        assert platform_block.element.type == "multi_static_select"

        # Check initial options
        assert len(platform_block.element.initial_options) == 2

    def test_multiple_choice_field_empty_initial(self):
        """Test MultipleChoiceField with no initial value."""

        class TestForm(forms.Form):
            platforms = forms.MultipleChoiceField(
                choices=[
                    ("FR", "France"),
                    ("DE", "Germany"),
                ],
                required=False,
            )

        slack_form = SlackForm(TestForm)()
        blocks = slack_form.slack_blocks()

        assert len(blocks) > 0

        # Find the platforms block
        platform_block = next(b for b in blocks if b.block_id == "platforms")

        # Should have no initial_options
        assert not hasattr(platform_block.element, "initial_options") or not platform_block.element.initial_options


@pytest.mark.django_db
class TestSlackViewSubmissionToDict:
    """Test parsing of multi-select responses from Slack."""

    def test_multi_static_select_parsing(self):
        """Test that multi_static_select responses are parsed as lists."""
        body = {
            "view": {
                "state": {
                    "values": {
                        "environment": {
                            "environment": {
                                "type": "multi_static_select",
                                "selected_options": [
                                    {"value": "uuid-1"},
                                    {"value": "uuid-2"},
                                ],
                            }
                        }
                    }
                }
            }
        }

        result = slack_view_submission_to_dict(body)

        assert "environment" in result
        assert isinstance(result["environment"], list)
        assert result["environment"] == ["uuid-1", "uuid-2"]

    def test_multi_static_select_empty(self):
        """Test that empty multi_static_select returns empty list."""
        body = {
            "view": {
                "state": {
                    "values": {
                        "environment": {
                            "environment": {
                                "type": "multi_static_select",
                                "selected_options": [],
                            }
                        }
                    }
                }
            }
        }

        result = slack_view_submission_to_dict(body)

        assert "environment" in result
        assert isinstance(result["environment"], list)
        assert result["environment"] == []

    def test_checkboxes_checked(self):
        """Test that checked checkboxes (BooleanField) return True."""
        body = {
            "view": {
                "state": {
                    "values": {
                        "is_key_account": {
                            "is_key_account": {
                                "type": "checkboxes",
                                "selected_options": [
                                    {"value": "True"},
                                ],
                            }
                        }
                    }
                }
            }
        }

        result = slack_view_submission_to_dict(body)

        assert "is_key_account" in result
        assert result["is_key_account"] is True

    def test_checkboxes_unchecked(self):
        """Test that unchecked checkboxes (BooleanField) return False."""
        body = {
            "view": {
                "state": {
                    "values": {
                        "is_key_account": {
                            "is_key_account": {
                                "type": "checkboxes",
                                "selected_options": [],
                            }
                        }
                    }
                }
            }
        }

        result = slack_view_submission_to_dict(body)

        assert "is_key_account" in result
        assert result["is_key_account"] is False

    def test_multiple_checkboxes(self):
        """Test that multiple checkboxes are parsed correctly."""
        body = {
            "view": {
                "state": {
                    "values": {
                        "is_key_account": {
                            "is_key_account": {
                                "type": "checkboxes",
                                "selected_options": [{"value": "True"}],
                            }
                        },
                        "is_seller_in_golden_list": {
                            "is_seller_in_golden_list": {
                                "type": "checkboxes",
                                "selected_options": [],  # Unchecked
                            }
                        }
                    }
                }
            }
        }

        result = slack_view_submission_to_dict(body)

        assert result["is_key_account"] is True
        assert result["is_seller_in_golden_list"] is False
