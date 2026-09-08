import unittest
import threading
from types import SimpleNamespace

from vagabondity_youtube_localizer.app import create_app


class FakeYouTubeClient:
    def __init__(self):
        self.page_videos = []
        self.all_videos_cache = []
        self.results_per_page = 10
        self.total_video_count = 0
        self.per_page_option_index = 0
        self.error_code = ""
        self.channel_thumbnail = ""
        self.channel_name = "Test channel"
        self.language_names_in_display_order = ["English", "Spanish"]
        self.code_to_name = {
            "en": "English",
            "es": "Spanish",
            "ru": "Russian",
        }
        self.videos_trimmed = 0
        self.videos_skipped = 0
        self.video_filter = "all"
        self.filtered_video_count = 0
        self.video_filter_counts = {"all": 0, "videos": 0, "shorts": 0}
        self.language_refreshes = []

    @property
    def num_pages(self):
        return self._num_pages if hasattr(self, "_num_pages") else 1

    @num_pages.setter
    def num_pages(self, value):
        self._num_pages = value

    def set_video_page(self, page):
        self.current_page = page
        return page

    def set_video_filter(self, video_filter):
        self.video_filter = video_filter

    def clear_video_cache(self):
        self.page_videos = []
        self.all_videos_cache = []

    def refresh_video_language_metadata(self, videos):
        self.language_refreshes.append([video.video_title for video in videos])
        return True


class FakeLocalizationService:
    def __init__(self):
        self.google_translator = FakeProvider("Google connected")
        self.deepl_translator = FakeProvider("DeepL connected")
        self.completed = threading.Event()

    def localize_videos(self, *args, **kwargs):
        self.last_request = args
        self.last_request_kwargs = kwargs
        progress_callback = kwargs.get("progress_callback")
        if progress_callback:
            progress_callback(
                {
                    "type": "item_started",
                    "video": args[0][0],
                    "language": args[1][0],
                    "stage": "preparing",
                }
            )
            progress_callback(
                {
                    "type": "item_finished",
                    "video": args[0][0],
                    "language": args[1][0],
                    "outcome": "succeeded",
                }
            )
        self.completed.set()


class FakeProvider:
    is_available = True

    def __init__(self, message):
        self.message = message

    def test_connection(self):
        return {
            "ok": True,
            "status": "connected",
            "message": self.message,
        }

    def get_usage(self):
        return {
            "status": "ready",
            "used": 12,
            "limit": 500_000,
            "remaining": 499_988,
            "message": "Test usage",
        }


class FakeUsageTracker:
    def get_google_usage(self):
        return {
            "status": "ready",
            "used": 34,
            "limit": 500_000,
            "remaining": 499_966,
            "period": "2026-09",
            "message": "Test usage",
        }


class AppTests(unittest.TestCase):
    def setUp(self):
        self.youtube = FakeYouTubeClient()
        self.localizer = FakeLocalizationService()
        self.app = create_app(
            self.youtube,
            self.localizer,
            usage_tracker=FakeUsageTracker(),
        )
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_home_page_renders_without_external_services(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test channel", response.data)
        self.assertIn(b"Vagabondity Walks", response.data)
        self.assertIn(b"images/vagabondity-walks-icon.png", response.data)
        self.assertIn(b"Shorts are determined by duration only", response.data)
        self.assertIn(b"Choose languages &amp; localize", response.data)
        self.assertIn(b'id="addLanguageBtn"', response.data)
        self.assertIn(b'id="sidebarAddLanguageBtn"', response.data)
        self.assertEqual(
            response.data.count(b'class="btn btn-primary add-language-btn"'),
            2,
        )
        self.assertIn(
            b'document.querySelectorAll(".add-language-btn")',
            response.data,
        )
        self.assertIn(b"disabled", response.data)
        self.assertIn(b'id="testProvidersBtn"', response.data)
        self.assertIn(b'id="usageProvidersBtn"', response.data)
        self.assertIn(b"Provider connections", response.data)
        self.assertIn(b'id="language-modal-title">Choose languages</h2>', response.data)
        self.assertIn(b'id="modalProviderName"', response.data)
        self.assertIn(b"Translation via", response.data)
        self.assertIn(b"modalProviderName.innerText = providerName", response.data)
        self.assertNotIn(b"Select at least one video below to continue.", response.data)
        self.assertNotIn(b"Target markets", response.data)
        self.assertNotIn(
            b"Select one or more languages for the chosen videos.",
            response.data,
        )
        self.assertIn(
            b'id="translateSelectedBtn"\n                    onclick="onClickTranslate()" disabled>Select at least one language</button>',
            response.data,
        )
        self.assertIn(b"selector.checked && !selector.disabled", response.data)
        self.assertNotIn(
            b'alert("Please select at least one video and one language.")',
            response.data,
        )

    def test_top_pagination_buttons_render(self):
        # When num_pages is 2 (e.g. app passes num_pages=2 to template), page 1 is the first page and page 1 is also the last page
        self.youtube.num_pages = 1
        self.youtube.current_page = 1
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # On page 1 of 1, both buttons are disabled
        self.assertEqual(response.data.count(b'class="top-page-btn is-disabled"'), 2)
        self.assertIn(
            b'class="top-page-number" aria-current="page" aria-label="Current page 1">1</span>',
            response.data,
        )

        # When num_pages is 3 (2 pages total: page 1 and page 2)
        self.youtube.num_pages = 2
        self.youtube.current_page = 1
        response_p1 = self.client.get("/")
        self.assertEqual(response_p1.status_code, 200)
        # On page 1 of 2: left is disabled, right links to page 2
        self.assertIn(
            b'href="/?page=2&amp;video_filter=all#videos-library"',
            response_p1.data,
        )

        self.youtube.current_page = 2
        response_p2 = self.client.get("/?page=2")
        self.assertEqual(response_p2.status_code, 200)
        # On page 2 of 2 (last page): left links to page 1, right is disabled
        self.assertIn(
            b'href="/?page=1&amp;video_filter=all#videos-library"',
            response_p2.data,
        )
        self.assertIn(b'class="top-page-btn is-disabled"', response_p2.data)
        self.assertIn(
            b'class="top-page-number" aria-current="page" aria-label="Current page 2">2</span>',
            response_p2.data,
        )

    def test_video_filter_is_applied(self):
        response = self.client.get("/?video_filter=videos")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.youtube.video_filter, "videos")
        self.assertIn(b"Full videos", response.data)
        self.assertIn(
            b"document.querySelectorAll('.page-link')",
            response.data,
        )
        self.assertNotIn(
            b".page-link, .video-filter-option",
            response.data,
        )

    def test_languages_are_grouped_into_collapsible_priority_tiers(self):
        self.youtube.language_names_in_display_order = [
            "English",
            "Korean",
            "Italian",
            "Hindi",
            "Vietnamese",
            "Hungarian",
        ]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="tier-1" open', response.data)
        self.assertIn(b"\xf0\x9f\x8c\x8d Global", response.data)
        self.assertIn(b"Largest global audiences", response.data)
        self.assertIn(b'id="tier-2"', response.data)
        self.assertNotIn(b'id="tier-2" open', response.data)
        self.assertIn(b"\xe2\xad\x90 Major", response.data)
        self.assertIn(b"Major national &amp; online audiences", response.data)
        self.assertIn(b'id="tier-3"', response.data)
        self.assertNotIn(b'id="tier-3" open', response.data)
        self.assertIn(b"\xf0\x9f\x93\x8d Regional", response.data)
        self.assertIn(b"Significant regional audiences", response.data)
        self.assertEqual(
            response.data.count(b'class="language-tier-select-all"'),
            3,
        )
        self.assertNotIn(b"Select all available languages", response.data)
        self.assertIn(b"toggleLanguageTierSelection(event, this)", response.data)
        self.assertIn(
            b"document.body.classList.add('language-modal-open')",
            response.data,
        )
        self.assertIn(
            b"document.body.classList.remove('language-modal-open')",
            response.data,
        )

    def test_all_videos_view_serializes_titles_as_javascript(self):
        self.youtube.results_per_page = -1
        self.youtube.all_videos_cache = [
            SimpleNamespace(id="video-id", video_title='A "quoted" title'),
        ]

        response = self.client.get("/?video_filter=all")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'vids.push("A \\"quoted\\" title");', response.data)

    def test_brand_icon_static_file_is_available(self):
        response = self.client.get(
            "/static/images/vagabondity-walks-icon.png"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")
        response.close()

    def test_source_language_is_rendered_for_a_video(self):
        self.youtube.page_videos = [
            SimpleNamespace(
                id="video-id",
                video_title="English source video",
                description="Description",
                thumbnail_url="thumbnail.jpg",
                current_languages=["ru"],
                language_names=[],
                default_language_code="en",
                default_language_name=None,
                num_languages=1,
            )
        ]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Source language", response.data)
        self.assertIn(b"English", response.data)
        self.assertIn(b"Default", response.data)
        self.assertIn(b"Russian", response.data)
        self.assertIn(b'class="video-text-button"', response.data)
        self.assertIn(b'onclick="toggleVideoSelection(this)"', response.data)
        self.assertIn(b'class="localization-count" type="button"', response.data)
        self.assertIn(b'onclick="showHideLanguages(this)"', response.data)
        self.assertIn(b'aria-controls="video-localizations-1"', response.data)
        self.assertIn(
            b"Click a title or description to select a video",
            response.data,
        )

    def test_full_description_is_available_for_responsive_line_clamping(self):
        description = ("A complete video description with natural word breaks. " * 5) + "Final words."
        self.youtube.page_videos = [
            SimpleNamespace(
                id="video-id",
                video_title="Long description video",
                description=description,
                thumbnail_url="thumbnail.jpg",
                current_languages=[],
                language_names=[],
                default_language_code="en",
                default_language_name="English",
                num_languages=0,
            )
        ]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Final words.", response.data)

    def test_localization_request_is_delegated(self):
        response = self.client.post(
            "/",
            json={
                "selected_videos": ["Video"],
                "selected_languages": ["Spanish"],
                "overwrite": True,
                "translation_provider": "deepl",
                "trim_checked": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        self.assertEqual(
            self.localizer.last_request,
            (["Video"], ["Spanish"], True, "deepl", False),
        )
        self.assertEqual(
            self.localizer.last_request_kwargs,
            {"selected_video_ids": None},
        )

    def test_localization_progress_endpoint_reports_completed_work(self):
        response = self.client.post(
            "/localizations",
            json={
                "selected_videos": ["Video"],
                "selected_languages": ["Spanish"],
                "translation_provider": "deepl",
            },
        )

        self.assertEqual(response.status_code, 202)
        job_id = response.get_json()["job_id"]
        self.assertTrue(self.localizer.completed.wait(1))

        progress = self.client.get(f"/localizations/{job_id}")
        payload = progress.get_json()
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["processed"], 1)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["remaining"], 0)
        self.assertEqual(payload["percent"], 100)

    def test_progress_page_markup_contains_live_counts(self):
        response = self.client.get("/")

        self.assertIn(b'id="progressBar"', response.data)
        self.assertIn(b'id="progressCurrentVideo"', response.data)
        self.assertIn(b'id="progressSucceeded"', response.data)
        self.assertIn(b'id="progressSkipped"', response.data)
        self.assertIn(b'id="progressFailed"', response.data)
        self.assertIn(b'id="loadingOverlayMessage"', response.data)
        self.assertIn(b'Updating video library', response.data)

    def test_done_reloads_the_current_video_page(self):
        response = self.client.get("/?page=4&video_filter=videos")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"loadingOverlay.style.display = 'flex';\n"
            b"        window.location.reload();",
            response.data,
        )

    def test_active_progress_endpoint_is_empty_without_a_run(self):
        response = self.client.get("/localizations/active")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"job": None})

    def test_provider_connections_are_checked_independently_without_youtube_update(self):
        google_response = self.client.post("/providers/google/test", json={})
        deepl_response = self.client.post("/providers/deepl/test", json={})

        self.assertEqual(google_response.status_code, 200)
        self.assertEqual(
            google_response.get_json(),
            {
                "ok": True,
                "status": "connected",
                "message": "Google connected",
            },
        )
        self.assertEqual(deepl_response.status_code, 200)
        self.assertEqual(
            deepl_response.get_json(),
            {
                "ok": True,
                "status": "connected",
                "message": "DeepL connected",
            },
        )
        self.assertFalse(hasattr(self.localizer, "last_request"))

    def test_provider_usage_is_returned_without_youtube_update(self):
        response = self.client.post("/providers/usage", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["google"]["used"], 34)
        self.assertEqual(response.get_json()["deepl"]["used"], 12)
        self.assertFalse(hasattr(self.localizer, "last_request"))

    def test_language_states_include_partial_localizations_and_source_language(self):
        self.youtube.page_videos = [
            SimpleNamespace(
                video_title="Video A",
                current_languages=["ru"],
                language_names=["Russian"],
                default_language_code="en",
                default_language_name="English",
            ),
            SimpleNamespace(
                video_title="Video B",
                current_languages=[],
                language_names=[],
                default_language_code="en",
                default_language_name="English",
            ),
        ]

        response = self.client.post(
            "/languages",
            json={
                "num": 2,
                "vidNames": ["Video A", "Video B"],
                "refresh": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["refreshed"])
        self.assertEqual(self.youtube.language_refreshes, [["Video A", "Video B"]])
        self.assertEqual(response.get_json()["selected_count"], 2)
        self.assertEqual(
            response.get_json()["language_states"]["Russian"],
            {"localized_count": 1, "default_count": 0},
        )
        self.assertEqual(
            response.get_json()["language_states"]["English"],
            {"localized_count": 0, "default_count": 2},
        )
        self.assertNotIn("Russian", response.get_json()["current_languages"])

    def test_language_states_match_duplicate_titles_by_video_id(self):
        self.youtube.page_videos = [
            SimpleNamespace(
                id="first-id",
                video_title="Same title",
                current_languages=["es"],
                language_names=["Spanish"],
                default_language_code="en",
                default_language_name="English",
            ),
            SimpleNamespace(
                id="second-id",
                video_title="Same title",
                current_languages=["ru"],
                language_names=["Russian"],
                default_language_code="en",
                default_language_name="English",
            ),
        ]

        response = self.client.post(
            "/languages",
            json={"videoIds": ["second-id"], "vidNames": ["Same title"]},
        )

        payload = response.get_json()
        self.assertEqual(payload["selected_count"], 1)
        self.assertEqual(payload["current_languages"], ["Russian"])
        self.assertNotIn("Spanish", payload["language_states"])


if __name__ == "__main__":
    unittest.main()
