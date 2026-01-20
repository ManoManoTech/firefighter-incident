from __future__ import annotations

from types import SimpleNamespace

from firefighter.slack.views.modals.postmortem import PostMortemModal


class TestPostMortemModal:
    @staticmethod
    def _get_text_blocks(view_dict: dict) -> list[str]:
        return [
            block.get("text", {}).get("text", "")
            for block in view_dict.get("blocks", [])
            if block.get("type") == "section"
        ]

    @staticmethod
    def _get_action_elements(view_dict: dict) -> list[dict]:
        elements: list[dict] = []
        for block in view_dict.get("blocks", []):
            if block.get("type") == "actions":
                elements.extend(block.get("elements", []))
        return elements

    @staticmethod
    def test_p1_p2_shows_auto_creation_message(mocker):
        incident = SimpleNamespace(id=123, needs_postmortem=True)

        # No existing PMs
        mocker.patch(
            "firefighter.slack.views.modals.postmortem._safe_has_relation",
            return_value=False,
            create=True,
        )

        view = PostMortemModal().build_modal_fn(incident)
        view_dict = view.to_dict()

        texts = TestPostMortemModal._get_text_blocks(view_dict)
        assert any(
            "automatically created when the incident reaches MITIGATED" in t
            for t in texts
        )
        # No manual-create button for mandatory PMs
        action_ids = [
            el.get("action_id")
            for el in TestPostMortemModal._get_action_elements(view_dict)
        ]
        assert "incident_create_postmortem_now" not in action_ids

    @staticmethod
    def test_p3_shows_optional_message_and_button(mocker):
        incident = SimpleNamespace(id=456, needs_postmortem=False)

        # No existing PMs
        mocker.patch(
            "firefighter.slack.views.modals.postmortem._safe_has_relation",
            return_value=False,
            create=True,
        )

        view = PostMortemModal().build_modal_fn(incident)
        view_dict = view.to_dict()

        texts = TestPostMortemModal._get_text_blocks(view_dict)
        assert any("P3 incident post-mortem is not mandatory" in t for t in texts)

        action_ids = [
            el.get("action_id")
            for el in TestPostMortemModal._get_action_elements(view_dict)
        ]
        assert "incident_create_postmortem_now" in action_ids
