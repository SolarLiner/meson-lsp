import logging
from logging import LogRecord

from pyls_jsonrpc.endpoint import Endpoint


class LanguageServerLoggingHandler(logging.Handler):
    def __init__(self, endpoint: Endpoint, level=logging.NOTSET):
        self.endpoint = endpoint
        super().__init__(level)

    def emit(self, record: LogRecord):
        if record.module.endswith("endpoint"):
            return  # Prevent notification loops
        self.endpoint.notify("window/showMessage", {
            'type': self._get_message_level(record.levelno),
            'message': self.format(record)
        })

    @staticmethod
    def _get_message_level(level):
        if level > logging.ERROR:
            return 1
        if level > logging.WARNING:
            return 2
        if level > logging.INFO:
            return 3
        return 4
