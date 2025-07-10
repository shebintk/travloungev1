# your_app/utils/slack_connector.py

import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings


SLACK_BOT_TOKEN = settings.SLACK_BOT_TOKEN
SLACK_CHANNEL = settings.SLACK_CHANNEL

class SlackConnector:
    def __init__(self):
        self.client = WebClient(token=SLACK_BOT_TOKEN)

    def send_message(self, message):
        try:
            response = self.client.chat_postMessage(
                channel=SLACK_CHANNEL,
                text=message
            )
            # print(f"Message sent: {response['message']['text']}")
        except SlackApiError as e:
            print(f"Slack API Error: {e.response['error']}")
