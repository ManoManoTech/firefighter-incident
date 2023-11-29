from __future__ import annotations

from typing import TYPE_CHECKING

from slack.views.modals.close import CloseModal, modal_close
from slack.views.modals.downgrade_workflow import (
    DowngradeWorkflowModal,
    modal_dowgrade_workflow,
)
from slack.views.modals.key_event_message import (  # XXX(dugab) move and rename (not a modal but a surface...)
    KeyEvents,
)
from slack.views.modals.open import OpenModal, modal_open
from slack.views.modals.opening import select_impact
from slack.views.modals.opening.check_current_incidents import (
    CheckCurrentIncidentsModal,
)
from slack.views.modals.opening.details import critical, normal
from slack.views.modals.opening.select_impact import modal_select_impact
from slack.views.modals.postmortem import PostMortemModal, modal_postmortem
from slack.views.modals.select import modal_select
from slack.views.modals.send_sos import SendSosModal, modal_send_sos
from slack.views.modals.status import StatusModal, modal_status
from slack.views.modals.trigger_oncall import OnCallModal, modal_trigger_oncall
from slack.views.modals.update import UpdateModal, modal_update
from slack.views.modals.update_roles import UpdateRolesModal, modal_update_roles
from slack.views.modals.update_status import UpdateStatusModal, modal_update_status

if TYPE_CHECKING:
    from slack.views.modals.base_modal.base import SlackModal

selectable_modals: list[type[SlackModal]] = [
    UpdateModal,
    UpdateRolesModal,
    OnCallModal,
    CloseModal,
    PostMortemModal,
    StatusModal,
    SendSosModal,
    DowngradeWorkflowModal,
]
