from __future__ import annotations

import enum
import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Never

from slack_sdk.models.blocks.basic_components import MarkdownTextObject
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.blocks.blocks import Block, SectionBlock
from slack_sdk.models.metadata import Metadata

from firefighter.slack.slack_app import DefaultWebClient, slack_client

if TYPE_CHECKING:
    from slack_sdk.web.client import WebClient
    from slack_sdk.web.slack_response import SlackResponse

    from firefighter.incidents.models.incident import Incident
logger = logging.getLogger(__name__)
VALID_ID_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")


class SlackMessageStrategy(enum.Enum):
    """Define how should the message be posted.

    - `append`: add the message to the channel, even if a message with the same type has already been posted.
    - `replace`: replace the last message with the same type (push new one, delete old one)
    - `update`: update in place the last message with the same type
    """

    APPEND = "append"
    REPLACE = "replace"
    UPDATE = "update"


class SlackMessageSurface(ABC):
    """Base class for Slack messages, which are sent to a channel or a user.

    This provides a common interface to send messages with text, blocks and metadata.

    This is helpful to send messages but also to save them in DB.
    """

    id: str
    strategy: SlackMessageStrategy = SlackMessageStrategy.APPEND
    """Alphanumeric ID, starting with a letter, that may contain underscores. """

    def __init__(self) -> None:
        if not self.id or self.id == "":
            logger.warning(f"No Slack message ID set for {self.__class__.__name__}.")
        # Check the ID is well-formed to be a Slack event_type: alphanumeric string, starting with a letter, containing underscore
        elif not VALID_ID_REGEX.match(self.id):
            logger.warning(
                f"Slack message ID {self.id} is not well formed for {self.__class__.__name__}."
            )

    def get_blocks(self) -> list[Block]:
        """Returns the blocks of the message.

        Returns:
            list[Block]: List of Slack Blocks for the message. Default is the text as a SectionBlock.
        """
        return [SectionBlock(text=self.get_text())]

    @abstractmethod
    def get_text(self) -> str:
        """Returns the text of the message."""
        raise NotImplementedError

    def get_metadata(self) -> Metadata:
        """The value of `event_type` should be an alphanumeric string, and human-readable. The value of this field may appear in the UI to developers, so keep this in mind when choosing a value. Developers should make an effort to name with the pattern <resource_name_singular> and <action_in_past_tense>
        See more https://api.slack.com/reference/metadata.

        Returns:
            Metadata: Slack Metadata for the message.
        """
        return Metadata(event_type=self.id, event_payload={"ff_type": self.id})

    def get_slack_message_options(self) -> dict[str, Any]:
        return {
            "unfurl_links": False,
        }

    def get_slack_message_params(
        self, *, blocks_as_dict: bool = False
    ) -> dict[str, Any]:
        blocks: list[Block] | list[dict[str, Any]]
        blocks = (
            [block.to_dict() for block in self.get_blocks()]
            if blocks_as_dict
            else self.get_blocks()
        )

        return {
            "blocks": blocks,
            "text": self.get_text(),
            "metadata": self.get_metadata().to_dict(),
            **self.get_slack_message_options(),
        }

    @slack_client
    def post_message(
        self,
        conversation_id: str,
        client: WebClient = DefaultWebClient,
        **kwargs: Never,
    ) -> SlackResponse:
        """Deprecated. Only use for Global Channel, until the global channel is set in DB."""
        return client.chat_postMessage(
            channel=conversation_id,
            **self.get_slack_message_params(),
        )


class SectionBlockUpdateIntent(SectionBlock):
    def __init__(self, incident: Incident, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.text = MarkdownTextObject(
            text="_Make an update with `/incident update` or this button :point_right:_"
        )

        self.accessory = ButtonElement(
            text="Update",
            action_id="open_modal_incident_update_status",
            value=str(incident.id),
        )
