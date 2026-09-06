"""Local usage tracking for providers that do not expose billing usage by API."""

import json
import os
import tempfile
from threading import RLock
from datetime import date
from pathlib import Path


GOOGLE_FREE_MONTHLY_CHARACTERS = 500_000
GOOGLE_MONTHLY_SAFETY_LIMIT = 490_000
DEFAULT_USAGE_PATH = Path("config/usage.json")


class GoogleUsageLimitError(RuntimeError):
    """The next request would exceed the monthly safety limit."""


class GoogleUsageTracker:
    """Reserve characters before this application sends them to Google."""

    _lock = RLock()

    def __init__(self, usage_path=DEFAULT_USAGE_PATH):
        self._usage_path = Path(usage_path)

    @staticmethod
    def _current_period():
        return date.today().strftime("%Y-%m")

    def _read(self):
        try:
            with self._usage_path.open(encoding="utf-8") as usage_file:
                data = json.load(usage_file)
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise ValueError("Invalid Google usage file; translation is blocked")
        if (
            not isinstance(data.get("period"), str)
            or type(data.get("google_characters")) is not int
            or data["google_characters"] < 0
            or type(data.get("safety_limit_enabled", True)) is not bool
        ):
            raise ValueError("Invalid Google usage file; translation is blocked")
        return data

    def _current_data(self):
        data = self._read()
        enabled = data.get("safety_limit_enabled", True)
        if data.get("period") != self._current_period():
            return {
                "period": self._current_period(), "google_characters": 0,
                "safety_limit_enabled": enabled,
            }
        return {
            "period": self._current_period(),
            "google_characters": max(0, int(data.get("google_characters", 0))),
            "safety_limit_enabled": enabled,
        }

    def set_safety_limit_enabled(self, enabled):
        """Save the protection preference without resetting accumulated usage."""
        if type(enabled) is not bool:
            raise ValueError("Protection must be true or false")
        with self._lock:
            data = self._current_data()
            data["safety_limit_enabled"] = enabled
            self._write(data)

    def record_google_characters(self, character_count):
        """Reserve usage before sending a request, including uncertain failures."""
        with self._lock:
            data = self._current_data()
            requested = max(0, int(character_count))
            if (
                data["safety_limit_enabled"]
                and data["google_characters"] + requested > GOOGLE_MONTHLY_SAFETY_LIMIT
            ):
                remaining = max(0, GOOGLE_MONTHLY_SAFETY_LIMIT - data["google_characters"])
                raise GoogleUsageLimitError(
                    "Google's 490,000-character monthly app limit would be exceeded "
                    f"({remaining:,} remaining; {requested:,} requested). "
                    "Choose DeepL, wait until next month, or disable protection in Usage to allow paid translations."
                )
            data["google_characters"] += requested
            self._write(data)

    def _write(self, data):
        self._usage_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self._usage_path.parent,
                prefix=".usage-", suffix=".tmp", delete=False,
            ) as usage_file:
                temporary_path = Path(usage_file.name)
                json.dump(data, usage_file)
                usage_file.flush()
                os.fsync(usage_file.fileno())
            os.replace(temporary_path, self._usage_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def get_google_usage(self):
        """Return the app-local Google character meter for the current month."""
        try:
            with self._lock:
                data = self._current_data()
        except (OSError, ValueError):
            return {
                "status": "error",
                "message": "Cannot read Google usage. Translation is blocked until the usage file is repaired.",
            }
        used = data["google_characters"]
        enabled = data["safety_limit_enabled"]
        limit = GOOGLE_MONTHLY_SAFETY_LIMIT if enabled else GOOGLE_FREE_MONTHLY_CHARACTERS
        return {
            "status": "ready",
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "safety_limit_enabled": enabled,
            "period": data["period"],
            "message": "Usage from this application during the current month.",
        }
