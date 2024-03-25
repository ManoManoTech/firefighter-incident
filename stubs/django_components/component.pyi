from _typeshed import Incomplete
from django.forms.widgets import MediaDefiningClass
from django.views import View
from django_components.component_registry import ComponentRegistry as ComponentRegistry
from django_components.component_registry import register as register
from django_components.component_registry import registry as registry
from django_components.logger import logger as logger
from django_components.templatetags.component_tags import (
    FILLED_SLOTS_CONTENT_CONTEXT_KEY as FILLED_SLOTS_CONTENT_CONTEXT_KEY,
)
from django_components.templatetags.component_tags import (
    DefaultFillContent as DefaultFillContent,
)
from django_components.templatetags.component_tags import FillContent as FillContent
from django_components.templatetags.component_tags import (
    FilledSlotsContext as FilledSlotsContext,
)
from django_components.templatetags.component_tags import (
    IfSlotFilledConditionBranchNode as IfSlotFilledConditionBranchNode,
)
from django_components.templatetags.component_tags import (
    NamedFillContent as NamedFillContent,
)
from django_components.templatetags.component_tags import SlotName as SlotName
from django_components.templatetags.component_tags import SlotNode as SlotNode
from django_components.utils import search as search

class SimplifiedInterfaceMediaDefiningClass(MediaDefiningClass):
    def __new__(
        mcs,  # noqa: N804
        name: Incomplete,
        bases: Incomplete,
        attrs: Incomplete,
    ) -> Incomplete: ...

class Component(View, metaclass=SimplifiedInterfaceMediaDefiningClass): ...
