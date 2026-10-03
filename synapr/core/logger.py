"""Zero-leakage, privacy-aware structured logging for Synapr."""

import logging
import re
import sys
from typing import Optional

# Pattern to redact API keys or authorization headers from logs
_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE),
    re.compile(r"(api[_\-]?key\s*[:=]\s*['\"]?)[A-Za-z0-9_\-\.]{8,}(['\"]?)", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9_\-]{20,})"),
    re.compile(r"(gsk_[A-Za-z0-9_\-]{20,})"),
]


class SanitizingFormatter(logging.Formatter):
    """Custom logging formatter that strips sensitive tokens and formats colors."""

    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pattern in _SECRET_PATTERNS:
            msg = pattern.sub(r"\1[REDACTED]", msg)

        # ANSI colorize if terminal output
        if sys.stdout.isatty():
            color = self.COLORS.get(record.levelno, "")
            return f"{color}{msg}{self.RESET}"
        return msg


def setup_logger(name: str = "synapr", level: int = logging.INFO) -> logging.Logger:
    """Configure and return the Synapr application logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = SanitizingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
