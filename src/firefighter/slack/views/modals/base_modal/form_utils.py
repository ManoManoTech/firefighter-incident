from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    TypeAlias,
    TypedDict,
    TypeVar,
    cast,
)
from uuid import UUID

from django import forms
from django.db import models
from django.db.models import Model
from django.utils import timezone
from slack_sdk.models.blocks.basic_components import Option, OptionGroup, TextObject
from slack_sdk.models.blocks.block_elements import (
    CheckboxesElement,
    DateTimePickerElement,
    InputInteractiveElement,
    PlainTextInputElement,
    SelectElement,
    StaticMultiSelectElement,
    UserSelectElement,
)
from slack_sdk.models.blocks.blocks import ActionsBlock, Block, InputBlock, SectionBlock

from firefighter.firefighter.utils import get_in
from firefighter.incidents.forms.utils import EnumChoiceField, GroupedModelChoiceField
from firefighter.incidents.models.user import User
from firefighter.slack.models.user import SlackUser

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)
TZ = timezone.get_current_timezone()


class SlackFormAttributesInput(TypedDict, total=False):
    multiline: bool
    placeholder: str


class SlackFormAttributesBlock(TypedDict, total=False):
    hint: str | None


class SlackFormAttributesWidget(TypedDict, total=False):
    label_from_instance: Callable[[Any], str]
    post_block: Block | None
    pre_block: Block | None


class SlackFormAttributes(TypedDict, total=False):
    input: SlackFormAttributesInput
    block: SlackFormAttributesBlock
    widget: SlackFormAttributesWidget


SlackFormAttributesDict: TypeAlias = dict[str, SlackFormAttributes]


T = TypeVar("T", bound=forms.Form)


class SlackForm(Generic[T]):
    slack_fields: SlackFormAttributesDict
    form: T
    form_class: type[T]

    def __init__(
        self,
        form: type[T],
        slack_fields: SlackFormAttributesDict | None = None,
    ):
        self.form_class = form

        if hasattr(form, "slack_fields") and form.slack_fields:  # type: ignore
            self.slack_fields = form.slack_fields  # type: ignore
        else:
            self.slack_fields = slack_fields or {}

    def __call__(self, *args: Any, **kwargs: Any) -> SlackForm[T]:
        self.form = self.form_class(*args, **kwargs)
        return self

    def slack_blocks(
        self,
        block_wrapper: Literal["section_accessory", "input", "action"] = "input",
    ) -> list[Block]:
        """Return the list of blocks from a SlackForm.

        Args:
            block_wrapper (str, optional): Type of blocks destination. Defaults to "input".

        Raises:
            ValueError: Raised if one of the initial value does not match the field type.

        Returns:
            list[Block]: The List of Slack Blocks.
        """
        blocks = []
        for field_name, f in self.form.fields.items():
            # Get the default data, from the form data, the field.initial or the form.initial
            f.initial = self.get_field_initial(field_name, f)

            slack_input_kwargs: dict[str, Any] = {}
            slack_block_kwargs: dict[str, Any] = {}

            # Set Field common args
            slack_block_kwargs["label"] = (f.label or field_name.title())[:2000]
            slack_block_kwargs["hint"] = f.help_text[:2000]
            slack_block_kwargs["optional"] = not f.required

            # Set custom Slack SDK fields
            post_block, pre_block = self._parse_field_slack_args(
                field_name, f, slack_input_kwargs, slack_block_kwargs
            )

            slack_input_element = self._get_input_element(
                f, field_name, slack_input_kwargs
            )
            if slack_input_element is None:
                continue
            blocks += self._wrap_field_in_block(
                block_wrapper,
                field_name,
                f,
                slack_block_kwargs,
                slack_input_element,
                post_block,
                pre_block,
            )
        return blocks

    def get_field_initial(self, field_name: str, f: forms.Field) -> Any:
        initial = None
        if not self.form.is_bound and self.form.data:
            initial = self.form.cleaned_data.get(field_name)
        else:
            initial = self.form.initial.get(field_name, f.initial)

        if callable(f.initial):
            initial = f.initial()
        return initial

    def _get_input_element(
        self, f: forms.Field, field_name: str, slack_input_kwargs: dict[str, Any]
    ) -> InputInteractiveElement | None:
        if isinstance(f.widget, forms.HiddenInput):
            return None
        match f:
            case forms.CharField():
                if not isinstance(f.initial, str) and f.initial is not None:
                    err_msg = f"Initial value for {field_name} is not a string or None"
                    raise ValueError(err_msg)
                return self._process_slack_char_field(field_name, f, slack_input_kwargs)
            case forms.SplitDateTimeField() | forms.DateTimeField():
                if (
                    not isinstance(f.initial, datetime | str | int)
                    and f.initial is not None
                ):
                    err_msg = f"Initial value for {field_name} is not a datetime, string, int or None"
                    raise ValueError(err_msg)
                return self._process_slack_splitdatetime_field(
                    field_name, f, slack_input_kwargs
                )
            case GroupedModelChoiceField():
                if not isinstance(f.initial, models.Model) and f.initial is not None:
                    err_msg = f"Initial value for {field_name} is not a model instance or None"
                    raise ValueError(err_msg)
                return self._process_slack_model_grouped_choice_field(
                    field_name, f, slack_input_kwargs
                )
            case forms.ModelMultipleChoiceField() | forms.MultipleChoiceField():
                return self._process_slack_multiple_choice_field(
                    field_name, f, slack_input_kwargs
                )
            case forms.ModelChoiceField() | forms.ChoiceField() | EnumChoiceField():
                if (
                    isinstance(f, forms.ModelChoiceField)
                    and f.queryset
                    and f.queryset.model == User
                    and (isinstance(f.initial, User) or f.initial is None)
                ):
                    return self._process_model_user_field(
                        field_name, f, slack_input_kwargs
                    )

                return self._process_slack_choice_field(
                    field_name, f, slack_input_kwargs
                )
            case forms.BooleanField():
                return self._process_slack_boolean_field(
                    field_name, f, slack_input_kwargs
                )
            case _:
                logger.warning(f"Field {field_name} of type {type(f)} not supported")
                return None

    @staticmethod
    def _wrap_field_in_block(
        block_wrapper: Literal["section_accessory", "input", "action"],
        field_name: str,
        f: forms.Field,
        slack_block_kwargs: dict[str, Any],
        slack_input_element: InputInteractiveElement,
        post_block: Block | None,
        pre_block: Block | None,
    ) -> list[Block]:
        blocks: list[Block] = []
        if pre_block:
            blocks.append(pre_block)
        if f.disabled:
            if f.label and isinstance(f.label, str):
                blocks.append(SectionBlock(text=f.label))
            if isinstance(f.initial, datetime):
                blocks.append(
                    SectionBlock(
                        text=str(
                            f.initial.astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z")
                            if f.initial
                            else "Not set"
                        )
                    )
                )
            else:
                blocks.append(
                    SectionBlock(text=str(f.initial) if f.initial else "Not set")
                )
        elif block_wrapper == "input":
            blocks.append(
                InputBlock(
                    element=slack_input_element,
                    block_id=field_name,
                    label=slack_block_kwargs.pop("label"),
                    **slack_block_kwargs,
                )
            )
        elif block_wrapper == "section_accessory":
            blocks.append(
                SectionBlock(
                    text=f"*{f.label}*\n{f.help_text}",
                    accessory=slack_input_element,
                )
            )
        elif block_wrapper == "action":
            if f.label and isinstance(f.label, str):
                blocks.append(SectionBlock(text=f.label))
            blocks.append(
                ActionsBlock(
                    elements=[slack_input_element],
                    block_id=field_name,
                    **slack_block_kwargs,
                )
            )
        if post_block:
            blocks.append(post_block)
        return blocks

    def _parse_field_slack_args(
        self,
        field_name: str,
        f: forms.Field,
        slack_input_kwargs: dict[str, Any],
        slack_block_kwargs: dict[str, Any],
    ) -> tuple[Block | None, Block | None]:
        post_block = None
        pre_block = None
        if hasattr(self, "slack_fields") and field_name in self.slack_fields:
            attributes = self.slack_fields[field_name]
            if "input" in attributes:
                input_args = attributes["input"]
                slack_input_kwargs.update(dict(input_args.items()))
            if "block" in attributes:
                block_args = attributes["block"]
                slack_block_kwargs.update(dict(block_args.items()))
            # Set Django field attributes
            if "widget" in attributes:
                widget_args = attributes["widget"]
                if "label_from_instance" in widget_args and isinstance(
                    f, forms.ModelChoiceField
                ):
                    f.label_from_instance = widget_args["label_from_instance"]  # type: ignore[method-assign,assignment]
                if "post_block" in widget_args:
                    post_block = widget_args["post_block"]
                if "pre_block" in widget_args:
                    pre_block = widget_args["pre_block"]
        return post_block, pre_block

    @classmethod
    def _process_slack_choice_field(
        cls,
        field_name: str,
        f: forms.ModelChoiceField | forms.ChoiceField,  # type: ignore[type-arg]
        slack_input_kwargs: dict[str, Any],
    ) -> InputInteractiveElement:
        if not isinstance(f, forms.ModelChoiceField | forms.ChoiceField):
            err_msg = f"Field {field_name} is not a ModelChoiceField or ChoiceField"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        if f.initial:
            initial_choice_label: str | None = None
            if isinstance(f, forms.ModelChoiceField):
                initial_choice_label = f.label_from_instance(f.initial)
                initial_choice_value = str(f.initial.pk)

            elif isinstance(f, EnumChoiceField):
                initial_choice_label = f.initial.label
                initial_choice_value = str(f.initial.value)

            elif isinstance(f, forms.ChoiceField):
                initial_choice_label = str(
                    [c[1] for c in f.choices if c[0] == f.initial][0]  # noqa: RUF015
                )
                initial_choice_value = f.initial
            else:
                err_msg = f"Field {field_name} is not a supported ChoiceField"  # type: ignore[unreachable]
                raise TypeError(err_msg)

            slack_input_kwargs["initial_option"] = SafeOption(
                label=initial_choice_label, value=initial_choice_value
            )

        slack_input_kwargs["options"] = [
            SafeOption(label=str(c[1]), value=str(c[0]))
            for c in filter(lambda co: co[0] != "", f.choices)
        ]
        # Add the initial option to the list of options if it's not there
        if (
            "initial_option" in slack_input_kwargs
            and slack_input_kwargs["initial_option"]
            not in slack_input_kwargs["options"]
        ):
            slack_input_kwargs["options"].append(slack_input_kwargs["initial_option"])

        # Ensure we have at least one option for Slack API
        if not slack_input_kwargs["options"]:
            slack_input_kwargs["options"] = [
                SafeOption(label="Please select an option", value="__placeholder__")
            ]

        field_name = f"{field_name}___{f.initial}{datetime.now().timestamp()}"  # noqa: DTZ005
        field_name = field_name[:254]
        return SelectElement(action_id=field_name, **slack_input_kwargs)

    @classmethod
    def _process_slack_multiple_choice_field(
        cls,
        field_name: str,
        f: forms.ModelMultipleChoiceField | forms.MultipleChoiceField,  # type: ignore[type-arg]
        slack_input_kwargs: dict[str, Any],
    ) -> InputInteractiveElement:
        """Process multiple choice fields (ModelMultipleChoiceField, MultipleChoiceField)."""
        if not isinstance(f, forms.ModelMultipleChoiceField | forms.MultipleChoiceField):
            err_msg = f"Field {field_name} is not a ModelMultipleChoiceField or MultipleChoiceField"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        # Handle initial values (list of objects or values)
        if f.initial:
            initial_options: list[SafeOption] = []
            # f.initial can be a list, queryset, or callable
            initial_value = f.initial() if callable(f.initial) else f.initial

            if isinstance(f, forms.ModelMultipleChoiceField):
                # For ModelMultipleChoiceField, initial is a list/queryset of model instances
                initial_options.extend(SafeOption(
                            label=f.label_from_instance(obj),
                            value=str(obj.pk),
                        ) for obj in initial_value)
            elif isinstance(f, forms.MultipleChoiceField):
                # For MultipleChoiceField, initial is a list of choice values
                for val in initial_value:
                    choice_label = str(next(c[1] for c in f.choices if c[0] == val))
                    initial_options.append(
                        SafeOption(label=choice_label, value=str(val))
                    )

            if initial_options:
                slack_input_kwargs["initial_options"] = initial_options

        # Build all options
        slack_input_kwargs["options"] = [
            SafeOption(label=str(c[1]), value=str(c[0]))
            for c in filter(lambda co: co[0] != "", f.choices)
        ]

        # Ensure we have at least one option for Slack API
        if not slack_input_kwargs["options"]:
            slack_input_kwargs["options"] = [
                SafeOption(label="Please select an option", value="__placeholder__")
            ]

        return StaticMultiSelectElement(action_id=field_name, **slack_input_kwargs)

    @classmethod
    def _process_model_user_field(
        cls,
        field_name: str,
        f: forms.ModelChoiceField,  # type: ignore[type-arg]
        slack_input_kwargs: dict[str, Any],
    ) -> InputInteractiveElement:
        if not isinstance(f, forms.ModelChoiceField):
            err_msg = f"Field {field_name} is not a ModelChoiceField"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        if f.initial:
            initial_user: User | None = SlackUser.objects.add_slack_id_to_user(
                user=f.initial
            )
            initial_user_slack_id = (
                initial_user.slack_user.slack_id
                if initial_user and initial_user.slack_user
                else None
            )
            slack_input_kwargs["initial_user"] = initial_user_slack_id

        field_name = f"{field_name}___{f.initial}{datetime.now().timestamp()}"  # noqa: DTZ005
        field_name = field_name[:254]
        return UserSelectElement(action_id=field_name, **slack_input_kwargs)

    @classmethod
    def _process_slack_model_grouped_choice_field(
        cls,
        field_name: str,
        f: GroupedModelChoiceField,
        slack_input_kwargs: dict[str, Any],
    ) -> SelectElement:
        if not isinstance(f, GroupedModelChoiceField):
            err_msg = f"Field {field_name} is not a GroupedModelChoiceField"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        if f.initial:
            slack_input_kwargs["initial_option"] = SafeOption(
                label=f.label_from_instance(f.initial),
                value=str(f.initial.pk),
            )

        slack_input_kwargs["option_groups"] = []
        for _, (option_group_value, option_group_label) in enumerate(f.choices):
            if option_group_value is None:
                option_group_value = ""  # noqa: PLW2901
                continue

            if isinstance(option_group_label, list | tuple):
                group_name = str(option_group_value)
                choices = option_group_label
                subgroup = [
                    SafeOption(label=str(option_label), value=str(option_value))
                    for option_value, option_label in choices
                ]

                slack_input_kwargs["option_groups"].append(
                    OptionGroup(label=str(group_name), options=subgroup)
                )

        # Ensure we have at least one option group for Slack API
        if not slack_input_kwargs["option_groups"]:
            slack_input_kwargs["option_groups"] = [
                OptionGroup(
                    label="No options available",
                    options=[SafeOption(label="Please select an option", value="__placeholder__")]
                )
            ]

        return SelectElement(action_id=field_name, **slack_input_kwargs)

    @classmethod
    def _process_slack_char_field(
        cls,
        field_name: str,
        f: forms.CharField,
        slack_input_kwargs: dict[str, Any],
    ) -> PlainTextInputElement:
        if not isinstance(f, forms.CharField):
            err_msg = f"Field {field_name} is not a CharField"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        if f.max_length:
            slack_input_kwargs["max_length"] = f.max_length
        if f.min_length:
            slack_input_kwargs["min_length"] = f.min_length

        if f.initial:
            slack_input_kwargs["initial_value"] = f.initial

        return PlainTextInputElement(
            action_id=field_name,
            **slack_input_kwargs,
        )

    @classmethod
    def _process_slack_boolean_field(
        cls,
        field_name: str,
        f: forms.BooleanField,
        slack_input_kwargs: dict[str, Any],
    ) -> CheckboxesElement:
        if not isinstance(f, forms.BooleanField):
            err_msg = f"Field {field_name} is not a BooleanField"  # type: ignore[unreachable]
            raise TypeError(err_msg)
        # Make a list with only one option "Yes" that maps to True
        slack_input_kwargs["options"] = [SafeOption(label="Yes", value="True")]
        if f.initial:
            slack_input_kwargs["initial_option"] = SafeOption(label="Yes", value="True")

        return CheckboxesElement(action_id=field_name, **slack_input_kwargs)

    @classmethod
    def _process_slack_splitdatetime_field(
        cls,
        field_name: str,
        f: forms.SplitDateTimeField | forms.DateTimeField,
        slack_input_kwargs: dict[str, Any],
    ) -> DateTimePickerElement:
        if not isinstance(f, forms.SplitDateTimeField | forms.DateTimeField):
            err_msg = f"Field {field_name} is not a SplitDateTimeField or DateTimeField"  # type: ignore[unreachable]
            raise TypeError(err_msg)

        if f.initial:
            slack_input_kwargs["initial_date_time"] = (
                int(f.initial.timestamp()) if isinstance(f.initial, datetime) else None
            )
            field_name = (
                field_name + "___" + str(datetime.now(timezone.utc).timestamp())  # type: ignore[attr-defined]
            )
            field_name = field_name[:254]
        return DateTimePickerElement(
            action_id=field_name,
            **slack_input_kwargs,
        )


def slack_view_submission_to_dict(
    body: dict[str, Any | str],
) -> dict[str, str | Any]:
    """Returns a dict of the form data from a Slack view submission."""
    if body.get("view"):
        path = ["view", "state", "values"]
    elif body.get("type") == "block_actions":
        path = ["state", "values"]
    else:
        logger.warning("Unknown Slack view submission format: %s", body)
        path = ["view", "state", "values"]

    values: dict[str, dict[str, Any]] = get_in(body, path)
    data: dict[str, str | Any] = {}
    if not isinstance(values, dict):
        raise TypeError("Expected a values dict in the body")

    # We expect only one action per input
    # The action_id must be block_id or block_id___{whatever}
    # We support block_id and block_id___{whatever} because Slack won't update the value in the user's form if the action_id is the same
    # Hence, we need to add a unique identifier to the action_id to force Slack to update the value, replacing the input by another one
    for block in values.values():
        if len(block) == 0:
            continue
        action_id: str = next(iter(block.keys()))
        action_id_stripped = action_id.split("___", 1)[0].strip()
        input_field = block.get(action_id)
        if not isinstance(input_field, dict):
            raise TypeError("Expected input_field to be a dict")

        if input_field.get("type") == "plain_text_input":
            data[action_id_stripped] = input_field.get("value")
        elif input_field.get("type") == "datetimepicker":
            data[action_id_stripped] = (
                datetime.fromtimestamp(
                    cast("float", input_field.get("selected_date_time")),
                    tz=TZ,
                )
                if input_field.get("selected_date_time")
                else None
            )
        elif input_field.get("type") == "static_select":
            data[action_id_stripped] = get_in(input_field, ["selected_option", "value"])
        elif input_field.get("type") == "multi_static_select":
            # Handle multiple selections - return list of values
            selected_options = input_field.get("selected_options", [])
            data[action_id_stripped] = [opt.get("value") for opt in selected_options]
        elif input_field.get("type") == "checkboxes":
            # Handle checkboxes (BooleanField) - return True if "True" is in selected_options
            selected_options = input_field.get("selected_options", [])
            # For BooleanField, we have only one option with value="True"
            data[action_id_stripped] = any(opt.get("value") == "True" for opt in selected_options)
        elif input_field.get("type") == "users_select":
            user_id = get_in(
                input_field,
                [
                    "selected_user",
                ],
            )
            user_obj = (
                SlackUser.objects.get_user_by_slack_id(slack_id=user_id)
                if user_id
                else None
            )
            data[action_id_stripped] = user_obj.id if user_obj else None
    return data


class SlackFormJSONEncoder(json.JSONEncoder):
    """JSON encoder that can handle UUIDs and Django models.
    Used to serialize the form data to JSON for Slack modal private_metadata.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Model):
            return o.pk
        if isinstance(o, UUID):
            return str(o)
        return super().default(o)


class SafeOption(Option):
    """Make sure we are creating valid Option, warn otherwise."""

    def __init__(
        self,
        *,
        value: str,
        label: str | None = None,
        text: str | dict[str, Any] | TextObject | None = None,  # Block Kit
        description: str | dict[str, Any] | TextObject | None = None,
        url: str | None = None,
        **others: dict[str, Any],
    ) -> None:
        if len(value) > 75:
            logger.warning("Option value is too long: %s", value)
            value = value[:75]
        if label and len(label) > 75:
            logger.warning("Option label is too long: %s", label)
            label = label[:74] + "…"
        super().__init__(
            value=value,
            label=label,
            text=text,
            description=description,
            url=url,
            **others,
        )
