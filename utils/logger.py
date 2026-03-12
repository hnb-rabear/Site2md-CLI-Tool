"""
utils/logger.py — Logging setup cho Site2MD
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(log_file: str = "error.log") -> logging.Logger:
    """Khởi tạo logger: INFO lên stdout, WARNING+ vào error.log (rotating)."""
    logger = logging.getLogger("site2md")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger  # Tránh duplicate handlers

    # Console handler — INFO trở lên
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))

    # File handler — WARNING trở lên, rotating (5MB x 3 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def log_skip(logger: logging.Logger, url: str, reason: str) -> None:
    """Ghi nhận URL bị bỏ qua vào error.log."""
    logger.warning("[SKIPPED] %s — %s", url, reason)


def log_error(logger: logging.Logger, url: str, error: Exception) -> None:
    """Ghi nhận lỗi khi crawl URL."""
    logger.warning("[ERROR] %s — %s: %s", url, type(error).__name__, error)
