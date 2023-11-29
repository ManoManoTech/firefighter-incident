from __future__ import annotations


class IncidentSelectableModalMixinBase:
    def get_select_title(self) -> str:
        raise NotImplementedError

    def get_select_modal_title(self) -> str:
        raise NotImplementedError
