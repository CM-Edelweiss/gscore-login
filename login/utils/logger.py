from __future__ import annotations

import logging
import sys
from datetime import datetime
from loguru import logger


class _InterceptHandler(logging.Handler):
    """把 stdlib logging（uvicorn / fastapi）转给 loguru，避免双格式。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "| <level>{level:<7}</level> | "
            # "<cyan>{name}:{function}:{line}</cyan> - "
            "<level>{message}</level>"
        ),
        enqueue=False,
    )
    logger.add(
        f'logs/{datetime.now().strftime("%Y-%m-%d")}.log',
        level=level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "| <level>{level:<7}</level> | "
            # "<cyan>{name}:{function}:{line}</cyan> - "
            "<level>{message}</level>"
        ),
        enqueue=False,
    )
    handler = _InterceptHandler()
    logging.basicConfig(handlers=[handler], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        target = logging.getLogger(name)
        target.handlers = [handler]
        target.propagate = False
