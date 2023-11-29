from __future__ import annotations

from slack.slack_app import SlackApp
from slack.views.events.channel_archive import channel_archive
from slack.views.events.channel_id_changed import channel_id_changed
from slack.views.events.channel_rename import conversation_rename
from slack.views.events.channel_shared import channel_shared
from slack.views.events.channel_unarchive import channel_unarchive
from slack.views.events.channel_unshared import channel_unshared
from slack.views.events.commands import manage_incident
from slack.views.events.home import update_home_tab
from slack.views.events.member_joined_channel import member_joined_channel
from slack.views.events.member_left_channel import member_left_channel
from slack.views.events.message import handle_message_events
from slack.views.events.message_deleted import handle_message_deleted
from slack.views.events.reaction_added import reaction_added

app = SlackApp()


@app.event("message")
def handle_message_events_ignore() -> None:
    """Ignore other message events.
    Must be the last event handler for message.
    """
    return
