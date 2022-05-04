from datetime import datetime
import logging
from logging.config import dictConfig
from os import environ

import json_log_formatter

LOG_LEVEL = environ.get("LOG_LEVEL", "INFO")


class CustomJSONFormatter(json_log_formatter.JSONFormatter):
    def json_record(self, message: str, extra: dict, record: logging.LogRecord) -> dict:
        extra["date"] = datetime.utcnow()
        extra["status"] = record.levelname  # remap status for datadog
        extra["filepath"] = record.pathname
        extra["function"] = record.funcName
        extra["line"] = record.lineno
        extra["logger.name"] = record.name
        extra["message"] = message
        return extra


logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": CustomJSONFormatter},
        "simple": {"format": "[%(levelname)-8s] %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "loggers": {
        "": {"handlers": ["console"], "level": LOG_LEVEL},
        "app": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

dictConfig(logging_config)
