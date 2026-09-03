"""Local usage tracking for providers that do not expose billing usage by API."""

import json
from datetime import date
from pathlib import Path


GOOGLE_FREE_MONTHLY_CHARACTERS = 500_000
DEFAULT_USAGE_PATH = Path("config/usage.json")


class GoogleUsageTracker:
    """Track characters successfully sent by this application to Google."""

    def __init__(self, usage_path=DEFAULT_USAGE_PATH):
        self._usage_path = Path(usage_path)

    @staticmethod
    def _current_period():
        return date.today().strftime("%Y-%m")

    def _read(self):
        try:
            with self._usage_path.open(encoding="utf-8") as usage_file:
                data = json.load(usage_file)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            data = {}
        return data if isinstance(data, dict) else {}

    def _current_data(self):
        data = self._read()
        if data.get("period") != self._current_period():
            return {"period": self._current_period(), "google_characters": 0}
        return {
            "period": self._current_period(),
            "google_characters": max(0, int(data.get("google_characters", 0))),
        }

    def record_google_characters(self, character_count):
        """Persist characters from a successful Google translation request."""
        data = self._current_data()
        data["google_characters"] += max(0, int(character_count))
        self._usage_path.parent.mkdir(parents=True, exist_ok=True)
        with self._usage_path.open("w", encoding="utf-8") as usage_file:
            json.dump(data, usage_file)

    def get_google_usage(self):
        """Return the app-local Google character meter for the current month."""
        used = self._current_data()["google_characters"]
        return {
            "status": "ready",
            "used": used,
            "limit": GOOGLE_FREE_MONTHLY_CHARACTERS,
            "remaining": max(0, GOOGLE_FREE_MONTHLY_CHARACTERS - used),
            "period": self._current_period(),
            "message": "Usage from this application during the current month.",
        }
