# isort: skip_file
from slack_bolt.adapter.django.handler import SlackRequestHandler

from slack.slack_app import SlackApp

app = SlackApp()
# pylint: disable=wrong-import-position
# noinspection PyPep8
from slack.views.events import actions_and_shortcuts, commands, home  # noqa: E402

# noinspection PyPep8
from slack.views.modals import *  # noqa: F403, E402

handler = SlackRequestHandler(app=app)
