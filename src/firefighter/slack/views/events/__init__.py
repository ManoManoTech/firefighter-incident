from __future__ import annotations

from firefighter.slack.slack_app import SlackApp
from firefighter.slack.views.events.channel_archive import channel_archive
from firefighter.slack.views.events.channel_id_changed import channel_id_changed
from firefighter.slack.views.events.channel_rename import conversation_rename
from firefighter.slack.views.events.channel_shared import channel_shared
from firefighter.slack.views.events.channel_unarchive import channel_unarchive
from firefighter.slack.views.events.channel_unshared import channel_unshared
from firefighter.slack.views.events.commands import manage_incident
from firefighter.slack.views.events.home import update_home_tab
from firefighter.slack.views.events.member_joined_channel import member_joined_channel
from firefighter.slack.views.events.member_left_channel import member_left_channel
from firefighter.slack.views.events.message import handle_message_events
from firefighter.slack.views.events.message_deleted import handle_message_deleted
from firefighter.slack.views.events.reaction_added import reaction_added

app = SlackApp()


@app.event("message")
def handle_message_events_ignore() -> None:
    """Ignore other message events.
    Must be the last event handler for message.
    """
    return
