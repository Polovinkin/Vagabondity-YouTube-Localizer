import time

from .translators import TranslationError


class LocalizationService:
    """Coordinate translations and publish them as YouTube localizations."""

    def __init__(self, youtube_client, google_translator, deepl_translator, delay=1):
        self.youtube_client = youtube_client
        self.google_translator = google_translator
        self.deepl_translator = deepl_translator
        self.delay = delay

    def localize_videos(
        self,
        selected_videos,
        selected_languages,
        overwrite,
        translation_provider,
        trim_checked,
    ):
        youtube = self.youtube_client
        youtube.videos_skipped = 0
        youtube.videos_trimmed = 0
        youtube.error_code = ""

        videos_to_search = (
            youtube.all_videos_cache
            if youtube.results_per_page == -1
            else youtube.page_videos
        )
        providers = {
            "google": self.google_translator,
            "deepl": self.deepl_translator,
        }
        provider = providers.get(translation_provider)
        if provider is None:
            youtube.videos_skipped += len(selected_videos) * len(selected_languages)
            print(f"Unknown translation provider '{translation_provider}'; skipped")
            return

        for video_title in selected_videos:
            target_video = self._find_video(videos_to_search, video_title)
            if target_video is None:
                youtube.videos_skipped += len(selected_languages)
                print(f"Video '{video_title}' was not found; skipped")
                continue

            for language in selected_languages:
                if language in target_video.language_names and not overwrite:
                    continue

                language_code = youtube.name_to_code.get(language.strip())
                if not language_code:
                    youtube.videos_skipped += 1
                    print(f"Unknown YouTube language '{language}'; skipped")
                    continue

                if not self._translate_and_publish(
                    provider,
                    target_video,
                    language,
                    language_code,
                    trim_checked,
                ):
                    youtube.videos_skipped += 1

                if youtube.error_code:
                    return

    def _translate_and_publish(
        self,
        provider,
        video,
        language,
        language_code,
        trim_checked,
    ):
        if not provider.is_available:
            print(
                f"{provider.name} is not configured; skipped "
                f"'{video.video_title}' for '{language}'"
            )
            return False

        try:
            if not provider.is_language_supported(language_code):
                print(f"{provider.name} does not support '{language}'; skipped")
                return False

            translated_title = provider.translate_text(
                video.video_title, language_code
            )
            translated_description = provider.translate_text(
                video.description, language_code
            )
        except TranslationError as exc:
            print(
                f"{provider.name} error for '{video.video_title}' "
                f"→ '{language}': {exc}; skipped"
            )
            return False

        print(f"{provider.name} completed '{video.video_title}' → '{language}'")
        published = self.youtube_client.set_video_localization(
            video.id,
            language_code,
            language,
            translated_title,
            translated_description,
            trim_checked,
            video.video_title,
        )
        if published is False:
            return False
        if self.delay:
            time.sleep(self.delay)
        return True

    @staticmethod
    def _find_video(videos, selected_title):
        normalized_title = selected_title.replace(" ", "")
        return next(
            (
                video
                for video in videos
                if str(video.video_title).replace(" ", "") == normalized_title
            ),
            None,
        )
