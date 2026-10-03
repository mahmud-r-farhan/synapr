"""Static paths and local-origin policy for the web dashboard."""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "static"
LOCAL_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$"
