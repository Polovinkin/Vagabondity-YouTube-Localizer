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
        selected_video_ids=None,
        progress_callback=None,
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
            for video_title in selected_videos:
                for language in selected_languages:
                    self._emit_finished(
                        progress_callback,
                        video_title,
                        language,
                        "skipped",
                        "unknown_provider",
                    )
            return

        selected_video_ids = selected_video_ids or []
        for index, video_title in enumerate(selected_videos):
            video_id = (
                selected_video_ids[index]
                if index < len(selected_video_ids)
                else None
            )
            target_video = self._find_video_by_id(videos_to_search, video_id)
            if target_video is None and video_id is None:
                target_video = self._find_video(videos_to_search, video_title)
            if target_video is None:
                youtube.videos_skipped += len(selected_languages)
                print(f"Video '{video_title}' was not found; skipped")
                for language in selected_languages:
                    self._emit_finished(
                        progress_callback,
                        video_title,
                        language,
                        "skipped",
                        "video_not_found",
                    )
                continue

            for language in selected_languages:
                self._emit(
                    progress_callback,
                    type="item_started",
                    video=target_video.video_title,
                    language=language,
                    stage="preparing",
                )
                default_language = getattr(
                    target_video, "default_language_name", None
                )
                if not default_language:
                    default_language = youtube.code_to_name.get(
                        getattr(target_video, "default_language_code", None)
                    )
                if language == default_language:
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "source_language",
                    )
                    continue

                if language in target_video.language_names and not overwrite:
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "already_localized",
                    )
                    continue

                language_code = youtube.name_to_code.get(language.strip())
                if not language_code:
                    youtube.videos_skipped += 1
                    print(f"Unknown YouTube language '{language}'; skipped")
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "unknown_language",
                    )
                    continue

                outcome, reason, trimmed = self._translate_and_publish(
                    provider,
                    target_video,
                    language,
                    language_code,
                    trim_checked,
                    progress_callback,
                )
                if outcome != "succeeded":
                    youtube.videos_skipped += 1
                self._emit_finished(
                    progress_callback,
                    target_video.video_title,
                    language,
                    outcome,
                    reason,
                    trimmed,
                )

                if youtube.error_code:
                    return

    def _translate_and_publish(
        self,
        provider,
        video,
        language,
        language_code,
        trim_checked,
        progress_callback=None,
    ):
        if not provider.is_available:
            print(
                f"{provider.name} is not configured; skipped "
                f"'{video.video_title}' for '{language}'"
            )
            return "skipped", "provider_unavailable", False

        try:
            if not provider.is_language_supported(language_code):
                print(f"{provider.name} does not support '{language}'; skipped")
                return "skipped", "unsupported_language", False

            self._emit_stage(progress_callback, video, language, "translating_title")
            translated_title = provider.translate_text(
                video.video_title, language_code
            )
            self._emit_stage(
                progress_callback, video, language, "translating_description"
            )
            translated_description = provider.translate_text(
                video.description, language_code
            )
        except TranslationError as exc:
            print(
                f"{provider.name} error for '{video.video_title}' "
                f"→ '{language}': {exc}; skipped"
            )
            return "failed", "translation_error", False

        print(f"{provider.name} completed '{video.video_title}' → '{language}'")
        self._emit_stage(progress_callback, video, language, "publishing")
        trimmed_before = self.youtube_client.videos_trimmed
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
            if self.youtube_client.error_code:
                return "failed", "youtube_error", False
            return "skipped", "text_too_long", False
        if self.delay:
            time.sleep(self.delay)
        was_trimmed = self.youtube_client.videos_trimmed > trimmed_before
        return "succeeded", None, was_trimmed

    @staticmethod
    def _emit(progress_callback, **event):
        if progress_callback:
            progress_callback(event)

    @classmethod
    def _emit_stage(cls, progress_callback, video, language, stage):
        cls._emit(
            progress_callback,
            type="stage",
            video=video.video_title,
            language=language,
            stage=stage,
        )

    @classmethod
    def _emit_finished(
        cls,
        progress_callback,
        video,
        language,
        outcome,
        reason=None,
        trimmed=False,
    ):
        cls._emit(
            progress_callback,
            type="item_finished",
            video=video,
            language=language,
            outcome=outcome,
            reason=reason,
            trimmed=trimmed,
        )

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

    @staticmethod
    def _find_video_by_id(videos, selected_id):
        if selected_id is None:
            return None
        return next(
            (video for video in videos if str(video.id) == str(selected_id)),
            None,
        )
