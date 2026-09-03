import unittest
from types import SimpleNamespace

from vagabondity_youtube_localizer.youtube_client import (
    LANGUAGE_FLAGS,
    Video,
    YouTubeClient,
    best_thumbnail_url,
    normalize_language_code,
    parse_iso8601_duration,
)


class VideoFilteringTests(unittest.TestCase):
    def test_highest_resolution_thumbnail_is_selected(self):
        thumbnails = {
            "default": {"url": "small.jpg"},
            "high": {"url": "high.jpg"},
            "maxres": {"url": "maxres.jpg"},
        }

        self.assertEqual(best_thumbnail_url(thumbnails), "maxres.jpg")
        self.assertEqual(best_thumbnail_url({}), "")

    def test_youtube_duration_is_converted_to_seconds(self):
        self.assertEqual(parse_iso8601_duration("PT2M59S"), 179)
        self.assertEqual(parse_iso8601_duration("PT1H2M3S"), 3723)
        self.assertIsNone(parse_iso8601_duration("not-a-duration"))

    def test_three_minute_video_is_treated_as_short(self):
        short = Video("Short", "short-id", "", "", [], 180)
        full_video = Video("Full", "full-id", "", "", [], 181)

        self.assertTrue(short.is_short)
        self.assertFalse(full_video.is_short)

    def test_filter_separates_shorts_and_full_videos(self):
        client = YouTubeClient.__new__(YouTubeClient)
        client.video_inventory = [
            Video("Short", "short-id", "", "", [], 60),
            Video("Full", "full-id", "", "", [], 600),
        ]

        client.video_filter = "shorts"
        self.assertEqual([video.id for video in client.filtered_videos], ["short-id"])

        client.video_filter = "videos"
        self.assertEqual([video.id for video in client.filtered_videos], ["full-id"])

    def test_language_flags_mapping_length_and_limit(self):
        client = YouTubeClient.__new__(YouTubeClient)
        client.code_to_name = {
            "en": "English",
            "es": "Spanish",
            "ru": "Russian",
            "fr": "French",
            "de": "German",
        }

        # Check each entry in LANGUAGE_FLAGS
        for lang_name, flags in LANGUAGE_FLAGS.items():
            # Flag emojis are regional indicator symbol pairs (2 unicode chars each, e.g. 🇺🇸 = 2 code points)
            # Count the number of flag characters by converting to list of emoji symbols
            # Or split by regional indicator pairs (each pair has length 2 in python str)
            self.assertTrue(len(flags) % 2 == 0, f"Flag sequence for {lang_name} has odd length")
            num_flags = len(flags) // 2
            self.assertGreaterEqual(num_flags, 1)
            self.assertLessEqual(num_flags, 3, f"Language {lang_name} has {num_flags} flags, expected <= 3")

    def test_language_locale_variants_are_normalized(self):
        self.assertEqual(normalize_language_code("ru-RU"), "ru")
        self.assertEqual(normalize_language_code("en-GB"), "en")
        self.assertEqual(normalize_language_code("zh-Hant"), "zh-TW")
        self.assertEqual(
            set(
                YouTubeClient._localization_codes(
                    {"localizations": {"ru-RU": {}, "en-GB": {}, "zh-Hant": {}}}
                )
            ),
            {"ru", "en", "zh-TW"},
        )

    def test_selected_video_language_metadata_is_refreshed(self):
        response = {
            "items": [
                {
                    "id": "video-id",
                    "snippet": {"defaultLanguage": "en-GB"},
                    "localizations": {"ru-RU": {}},
                }
            ]
        }

        class FakeVideosResource:
            def __init__(self):
                self.request = None

            def list(self, **kwargs):
                self.request = kwargs
                return SimpleNamespace(execute=lambda: response)

        resource = FakeVideosResource()
        client = YouTubeClient.__new__(YouTubeClient)
        client.youtube = SimpleNamespace(videos=lambda: resource)
        client.code_to_name = {"en": "English", "ru": "Russian"}
        video = SimpleNamespace(id="video-id")

        self.assertTrue(client.refresh_video_language_metadata([video]))
        self.assertEqual(resource.request["part"], "snippet,localizations")
        self.assertEqual(video.current_languages, ["ru"])
        self.assertEqual(video.default_language_code, "en")
        self.assertEqual(video.default_language_name, "English")


if __name__ == "__main__":
    unittest.main()
