"""Logging helpers for applications embedding the SDK."""

from __future__ import annotations

import logging

LOGGER_NAME = "firmngin"


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


__all__ = ["LOGGER_NAME", "get_logger"]
