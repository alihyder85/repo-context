"""Logging configuration for the code indexer."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from code_indexer.utils.config import settings


def setup_logging(log_level: Optional[str] = None, log_file: Optional[str] = None) -> None:
    """Setup logging configuration.

    Args:
        log_level: Override log level from config
        log_file: Override log file path from config
    """
    # Remove default handler
    logger.remove()

    # Determine log level
    level = log_level or settings.log_level

    # Determine log file
    log_path = log_file or settings.log_file
    if log_path:
        log_dir = Path(log_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    # Add console handler
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Add file handler if specified
    if log_path:
        logger.add(
            log_path,
            level=level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="1 week",
            encoding="utf-8",
        )


def get_logger(name: str) -> logger:
    """Get a logger instance for a specific module.

    Args:
        name: Module name

    Returns:
        Logger instance
    """
    return logger.bind(name=name)