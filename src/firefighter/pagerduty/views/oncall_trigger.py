from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views import generic

from firefighter.pagerduty.forms.create_pagerduty_incident import (
    CreatePagerDutyIncidentFreeForm,
)
from firefighter.pagerduty.tasks.trigger_oncall import trigger_oncall
from firefighter.slack.models.conversation import Conversation

if TYPE_CHECKING:
    from django.http import HttpResponse

    from firefighter.firefighter.utils import HtmxHttpRequest
logger = logging.getLogger(__name__)


class CreatePagerDutyIncidentFreeView(
    LoginRequiredMixin, generic.FormView[CreatePagerDutyIncidentFreeForm]
):
    form_class = CreatePagerDutyIncidentFreeForm
    success_url = reverse_lazy("pagerduty:oncall-list")

    def get_template_names(self) -> list[str]:
        request = cast("HtmxHttpRequest", self.request)
        if request.htmx and not request.htmx.boosted:
            template_name = "partials/trigger_oncall_form_view_modal.html"
        else:
            template_name = "pages/oncall_trigger.html"

        return [template_name]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Trigger on-call"
        return context

    def form_valid(self, form: CreatePagerDutyIncidentFreeForm) -> HttpResponse:
        incident_key = form.cleaned_data["title"].replace(" ", "_").lower()[0:255]
        conference = Conversation.objects.get_or_none(tag="tech_incidents")
        conference_url = settings.BASE_URL if conference is None else conference.link
        try:
            # XXX Maybe do more one day with the response!
            trigger_oncall(
                title=form.cleaned_data["title"],
                oncall_service=form.cleaned_data["service"],
                details=form.cleaned_data["details"],
                triggered_by=self.request.user,  # type: ignore
                incident_key=incident_key,
                conference_url=conference_url,
            )
        except Exception:  # XXX Do not catch blindly
            logger.exception("On-call trigger failed!")
            messages.error(self.request, "On-call trigger failed!")
            return super().form_valid(form)
        messages.success(self.request, "On-call triggered")
        return super().form_valid(form)
