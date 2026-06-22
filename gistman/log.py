"""Logging configuration via loguru.

Usage:
    from gistman.log import logger
    logger.info("Gist {} created", gist_id)
    logger.debug("Cache stale, refreshing...")
    try: ...
    except Exception: logger.exception("Refresh failed")
"""

import sys
from pathlib import Path

from loguru import logger as _base_logger

from gistman.constants import LOG_FILE

# Remove default stderr handler and add our own
_base_logger.remove()

# Console: show INFO+ with colour (ERROR and above highlighted)
_base_logger.add(
    sys.stderr,
    format="<level>{level.icon}</level> <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# File: full DEBUG+ with timestamp, module, line, for troubleshooting
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_base_logger.add(
    str(LOG_FILE),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name}:{function}:{line} | {message}",
    level="DEBUG",
    rotation="1 MB",
    retention=3,
    encoding="utf-8",
)

logger = _base_logger

__all__ = ["logger"]
