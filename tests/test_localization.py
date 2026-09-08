import unittest
from types import SimpleNamespace

from vagabondity_youtube_localizer.localization import LocalizationService
from vagabondity_youtube_localizer.translators import TranslationError
from vagabondity_youtube_localizer.youtube_client import YouTubeClient


class FakeYouTubeClient:
    def __init__(self):
        video = SimpleNamespace(
            id="video-id",
            video_title="Taipei Walk",
            description="A city walk",
            language_names=[],
            default_language_code="en",
            default_language_name="English",
        )
        self.page_videos = [video]
        self.all_videos_cache = []
        self.results_per_page = 10
        self.name_to_code = {"Spanish": "es"}
        self.videos_skipped = 0
        self.videos_trimmed = 0
        self.error_code = ""
        self.updates = []

    def set_video_localization(self, *args):
        self.updates.append(args)


class FakeTranslator:
    def __init__(self, name="Fake", available=True, supported=True, error=None):
        self.name = name
        self.is_available = available
        self.supported = supported
        self.error = error

    def is_language_supported(self, language_code):
        return self.supported

    def translate_text(self, text, target_language, source_language):
        if self.error:
            raise TranslationError(self.error)
        return f"{text} ({target_language})"


class LocalizationServiceTests(unittest.TestCase):
    def test_successful_translation_is_published(self):
        youtube = FakeYouTubeClient()
        google = FakeTranslator(name="Google")
        service = LocalizationService(youtube, google, FakeTranslator(), delay=0)

        service.localize_videos(
            ["Taipei Walk"], ["Spanish"], False, "google", False
        )

        self.assertEqual(youtube.videos_skipped, 0)
        self.assertEqual(len(youtube.updates), 1)
        self.assertEqual(youtube.updates[0][3], "Taipei Walk (es)")

    def test_progress_reports_each_stage_and_success(self):
        youtube = FakeYouTubeClient()
        service = LocalizationService(
            youtube, FakeTranslator(name="Google"), FakeTranslator(), delay=0
        )
        events = []

        service.localize_videos(
            ["Taipei Walk"],
            ["Spanish"],
            False,
            "google",
            False,
            progress_callback=events.append,
        )

        self.assertEqual(
            [event.get("stage") for event in events[:-1]],
            [
                "preparing",
                "translating_title",
                "translating_description",
                "publishing",
            ],
        )
        self.assertEqual(events[-1]["type"], "item_finished")
        self.assertEqual(events[-1]["outcome"], "succeeded")
        self.assertEqual(events[-1]["video"], "Taipei Walk")
        self.assertEqual(events[-1]["language"], "Spanish")

    def test_existing_localization_is_reported_as_skipped(self):
        youtube = FakeYouTubeClient()
        youtube.page_videos[0].language_names = ["Spanish"]
        service = LocalizationService(
            youtube, FakeTranslator(name="Google"), FakeTranslator(), delay=0
        )
        events = []

        service.localize_videos(
            ["Taipei Walk"],
            ["Spanish"],
            False,
            "google",
            False,
            progress_callback=events.append,
        )

        self.assertEqual(events[-1]["outcome"], "skipped")
        self.assertEqual(events[-1]["reason"], "already_localized")
        self.assertEqual(youtube.updates, [])

    def test_provider_error_is_not_published(self):
        youtube = FakeYouTubeClient()
        google = FakeTranslator(name="Google", error="simulated failure")
        service = LocalizationService(youtube, google, FakeTranslator(), delay=0)

        service.localize_videos(
            ["Taipei Walk"], ["Spanish"], False, "google", False
        )

        self.assertEqual(youtube.videos_skipped, 1)
        self.assertEqual(youtube.updates, [])

    def test_source_language_is_not_added_as_a_localization(self):
        youtube = FakeYouTubeClient()
        service = LocalizationService(
            youtube, FakeTranslator(name="Google"), FakeTranslator(), delay=0
        )

        service.localize_videos(
            ["Taipei Walk"], ["English"], False, "google", False
        )

        self.assertEqual(youtube.videos_skipped, 0)
        self.assertEqual(youtube.updates, [])

    def test_duplicate_titles_are_resolved_by_video_id(self):
        youtube = FakeYouTubeClient()
        youtube.page_videos.append(
            SimpleNamespace(
                id="second-video-id",
                video_title="Taipei Walk",
                description="Second description",
                language_names=[],
                default_language_code="en",
                default_language_name="English",
            )
        )
        service = LocalizationService(
            youtube, FakeTranslator(name="Google"), FakeTranslator(), delay=0
        )

        service.localize_videos(
            ["Taipei Walk"],
            ["Spanish"],
            False,
            "google",
            False,
            selected_video_ids=["second-video-id"],
        )

        self.assertEqual(youtube.updates[0][0], "second-video-id")


class LocalizationTextLimitTests(unittest.TestCase):
    def test_title_is_shortened_at_a_word_boundary(self):
        title = "A title with a meaningful final word that is too long" * 3

        shortened, was_shortened = YouTubeClient._shorten_title(title)

        self.assertTrue(was_shortened)
        self.assertLessEqual(len(shortened), 100)
        self.assertTrue(shortened.endswith("…"))

    def test_description_is_limited_by_utf8_bytes(self):
        description = ("Прогулка по ночному городу ") * 300

        shortened, was_shortened = YouTubeClient._shorten_description(description)

        self.assertTrue(was_shortened)
        self.assertLessEqual(len(shortened.encode("utf-8")), 5000)
        self.assertTrue(shortened.endswith("…"))


if __name__ == "__main__":
    unittest.main()
