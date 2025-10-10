from __future__ import annotations

from typing import TYPE_CHECKING

from firefighter.slack.views.modals.close import CloseModal, modal_close
from firefighter.slack.views.modals.closure_reason import (
    ClosureReasonModal,
    modal_closure_reason,
)
from firefighter.slack.views.modals.downgrade_workflow import (
    DowngradeWorkflowModal,
    modal_dowgrade_workflow,
)
from firefighter.slack.views.modals.edit import EditMetaModal, modal_edit
from firefighter.slack.views.modals.key_event_message import (  # XXX(dugab) move and rename (not a modal but a surface...)
    KeyEvents,
)
from firefighter.slack.views.modals.open import OpenModal, modal_open
from firefighter.slack.views.modals.opening import select_impact
from firefighter.slack.views.modals.opening.check_current_incidents import (
    CheckCurrentIncidentsModal,
)
from firefighter.slack.views.modals.opening.select_impact import modal_select_impact
from firefighter.slack.views.modals.postmortem import PostMortemModal, modal_postmortem
from firefighter.slack.views.modals.select import modal_select
from firefighter.slack.views.modals.send_sos import SendSosModal, modal_send_sos
from firefighter.slack.views.modals.status import StatusModal, modal_status
from firefighter.slack.views.modals.trigger_oncall import (
    OnCallModal,
    modal_trigger_oncall,
)
from firefighter.slack.views.modals.update import UpdateModal, modal_update
from firefighter.slack.views.modals.update_roles import (
    UpdateRolesModal,
    modal_update_roles,
)
from firefighter.slack.views.modals.update_status import (
    UpdateStatusModal,
    modal_update_status,
)

if TYPE_CHECKING:
    from firefighter.slack.views.modals.base_modal.base import SlackModal

selectable_modals: list[type[SlackModal]] = [
    UpdateModal,
    EditMetaModal,
    UpdateRolesModal,
    OnCallModal,
    CloseModal,
    PostMortemModal,
    StatusModal,
    SendSosModal,
    DowngradeWorkflowModal,
]
