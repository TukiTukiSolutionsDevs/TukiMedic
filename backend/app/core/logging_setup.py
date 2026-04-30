"""Structured logging configuration (T3.10).

Production: emits one JSON object per line on stdout. This is what every
log shipper (CloudWatch, Loki, Datadog, etc.) expects.

Development: human-readable single-line text — easier on the eyes when
running uvicorn locally.

Activated automatically via app.core.logging_setup.configure_logging() at
boot. Default level is INFO. Override with LOG_LEVEL env var.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Minimal structured formatter — no third-party deps."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Standard library puts a few useful identifiers on the record.
        for key in ("module", "funcName", "lineno"):
            payload[key] = getattr(record, key)
        # Anything the caller stuffed into `extra={...}`
        for k, v in record.__dict__.items():
            if k.startswith("_") or k in payload or k in (
                "args", "msg", "levelname", "levelno", "pathname", "filename",
                "exc_info", "exc_text", "stack_info", "created", "msecs",
                "relativeCreated", "thread", "threadName", "processName",
                "process", "name",
            ):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Idempotent — safe to call from main.py and tests' conftest."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    env = os.environ.get("ENVIRONMENT", "development").lower()
    use_json = env in {"production", "staging"}

    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )

    root = logging.getLogger()
    # Remove any pre-existing handlers (uvicorn installs its own; we override).
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(level)

    # Quiet down chatty libraries unless DEBUG is requested.
    if level > logging.DEBUG:
        for noisy in ("httpx", "httpcore", "openai", "anthropic", "boto3", "botocore"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
