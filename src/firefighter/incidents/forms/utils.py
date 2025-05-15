from __future__ import annotations

import logging
import operator
from functools import partial
from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from django.db import models
from django.forms import TypedChoiceField, ValidationError
from django.forms.models import ModelChoiceField, ModelChoiceIterator

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator

    from django.db.models import QuerySet
    from django.forms.models import ModelChoiceIteratorValue

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=models.Choices)


class GroupedModelChoiceIterator(ModelChoiceIterator):
    def __init__(
        self,
        field: ModelChoiceField,  # type: ignore[type-arg]
        group_by: operator.attrgetter[Any] | Callable[[Any], Any],
    ):
        self.groupby = group_by
        super().__init__(field)

    def __iter__(  # type: ignore[override]
        self,
    ) -> Generator[
        tuple[Any | Literal[""], list[tuple[ModelChoiceIteratorValue, str]] | str],
        Any,
        None,
    ]:
        if self.field.empty_label is not None:
            yield "", str(self.field.empty_label)
        queryset: QuerySet[Any] | Iterator[Any] | None = self.queryset
        if queryset is None:
            raise AttributeError(
                "Iterator has no queryset. Did you pass "
                "in an iterable of choices instead?"
            )
        # Can't use iterator() when queryset uses prefetch_related()
        if not queryset._prefetch_related_lookups:  # type: ignore # noqa: SLF001
            queryset = queryset.iterator()  # type: ignore
        for group, objs in groupby(queryset, self.groupby):
            yield group, [self.choice(obj) for obj in objs]


class GroupedModelChoiceField(ModelChoiceField):  # type: ignore[type-arg]
    iterator: partial[GroupedModelChoiceIterator]  # type: ignore[assignment]

    def __init__(
        self, *args: Any, choices_groupby: str | Callable[[Any], Any], **kwargs: Any
    ) -> None:
        if isinstance(choices_groupby, str):
            choices_groupby = attrgetter(choices_groupby)
        elif not callable(choices_groupby):
            raise TypeError(
                "choices_groupby must either be a str or a callable accepting a single argument"
            )
        self.iterator = partial(GroupedModelChoiceIterator, group_by=choices_groupby)
        super().__init__(*args, **kwargs)


class EnumChoiceField(TypedChoiceField):
    def __init__(self, *args: Any, enum_class: type[T], **kwargs: Any) -> None:
        # Explicit for type checking
        self.coerce_func: Callable[[Any], T] = lambda val: enum_class(  # noqa: PLW0108
            val
        )
        self.enum_class = enum_class
        if "choices" not in kwargs:
            kwargs["choices"] = enum_class.choices
        super().__init__(*args, coerce=self.coerce_func, **kwargs)

    def to_python(self, value: Any) -> int | str | Any:
        """Return a value from the enum class."""
        if value in self.empty_values:
            return ""
        # Cast to int if it's a string representation of an int
        if isinstance(value, str) and value.isdigit():
            value = int(value)

        # If value is already a valid enum member, return it
        if isinstance(value, self.enum_class):
            return value
        try:
            return self.coerce_func(value)
        except ValueError as exc:
            err_msg = f"{value} is not a valid {self.enum_class.__name__}"
            raise ValidationError(err_msg, code="invalid_choice") from exc
