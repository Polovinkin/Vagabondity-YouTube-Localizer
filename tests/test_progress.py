import unittest

from vagabondity_youtube_localizer.progress import LocalizationProgressTracker


class LocalizationProgressTrackerTests(unittest.TestCase):
    def test_counts_outcomes_reasons_and_remaining_work(self):
        tracker = LocalizationProgressTracker()
        job_id, _ = tracker.start(2, 2, "deepl")

        tracker.update(
            job_id,
            {
                "type": "item_finished",
                "video": "Video A",
                "language": "Spanish",
                "outcome": "succeeded",
                "trimmed": True,
            },
        )
        tracker.update(
            job_id,
            {
                "type": "item_finished",
                "video": "Video A",
                "language": "German",
                "outcome": "skipped",
                "reason": "text_too_long",
            },
        )

        job = tracker.get(job_id)
        self.assertEqual(job["processed"], 2)
        self.assertEqual(job["succeeded"], 1)
        self.assertEqual(job["skipped"], 1)
        self.assertEqual(job["failed"], 0)
        self.assertEqual(job["trimmed"], 1)
        self.assertEqual(job["remaining"], 2)
        self.assertEqual(job["percent"], 50)
        self.assertEqual(job["skip_reasons"], {"text_too_long": 1})

    def test_only_one_run_can_be_active(self):
        tracker = LocalizationProgressTracker()
        first_id, _ = tracker.start(1, 1, "google")

        self.assertEqual(tracker.get_active()["id"], first_id)

        second_id, active_job = tracker.start(1, 1, "deepl")

        self.assertIsNone(second_id)
        self.assertEqual(active_job["id"], first_id)
        tracker.finish(first_id)
        self.assertIsNone(tracker.get_active())
        third_id, _ = tracker.start(1, 1, "deepl")
        self.assertIsNotNone(third_id)


if __name__ == "__main__":
    unittest.main()
