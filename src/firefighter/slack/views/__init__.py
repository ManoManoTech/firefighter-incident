# isort: skip_file
from slack_bolt.adapter.django.handler import SlackRequestHandler

from firefighter.slack.slack_app import SlackApp

app = SlackApp()
# pylint: disable=wrong-import-position
# noinspection PyPep8
from firefighter.slack.views.events import (  # noqa: E402
    actions_and_shortcuts,
    commands,
    home,
)

# noinspection PyPep8
from firefighter.slack.views.modals import *  # noqa: F403, E402

handler = SlackRequestHandler(app=app)
