"""Structured JSON logging (OpenTelemetry-compatible field names).

Call configure_logging() once at application startup.  Every logger in the
process will then emit JSON to stdout.

OTel field mapping:
  timestamp    — ISO 8601 UTC instant derived from the log record's creation time
  severity     — OTel severity text: DEBUG | INFO | WARN | ERROR | FATAL
  body         — formatted log message
  service.name — "human-rating-platform"
  attributes   — any extra dict passed via extra={"attributes": {...}}

Usage:
    configure_logging(settings.app.log_level)

Log level is controlled by APP__LOG_LEVEL env var (or [app] log_level in
config.toml).  Accepted values: DEBUG, INFO, WARNING, ERROR.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_LEVEL_TO_SEVERITY: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARN",
    "ERROR": "ERROR",
    "CRITICAL": "FATAL",
}

SERVICE_NAME = "human-rating-platform"


class _OtelJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        attributes = getattr(record, "attributes", None)

        if record.exc_info and record.exc_info[0] is not None:
            exc_text = self.formatException(record.exc_info)
            attributes = dict(attributes) if attributes else {}
            attributes["exception"] = exc_text

        entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "severity": _LEVEL_TO_SEVERITY.get(record.levelname, record.levelname),
            "body": record.getMessage(),
            "service.name": SERVICE_NAME,
            "logger": record.name,
        }
        if attributes:
            entry["attributes"] = attributes

        return json.dumps(entry, default=str)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON to stdout.

    Replaces any existing handlers so this can safely be called once at
    startup without duplicating output.  The log_level should come from
    settings.app.log_level (env override: APP__LOG_LEVEL).
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_OtelJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
