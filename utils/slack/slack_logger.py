# your_app_name/utils/slack_logger.py

import logging
from .slack_connector import SlackConnector

class SlackErrorHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        slack = SlackConnector()
        slack.send_message(f":rotating_light: *ERROR ALERT*: \n```{log_entry}```")
