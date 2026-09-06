import tempfile
import unittest
from pathlib import Path

from vagabondity_youtube_localizer.usage import GoogleUsageTracker


class GoogleUsageTrackerTests(unittest.TestCase):
    def test_reserves_google_characters_for_the_current_month(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = GoogleUsageTracker(Path(temp_dir) / "usage.json")
            tracker.record_google_characters(123)
            tracker.record_google_characters(45)

            usage = tracker.get_google_usage()

        self.assertEqual(usage["used"], 168)
        self.assertEqual(usage["remaining"], 489_832)


if __name__ == "__main__":
    unittest.main()
