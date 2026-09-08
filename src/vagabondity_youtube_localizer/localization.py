import time

from .translators import TranslationError
from .translators.base import MonthlyTranslationLimitError


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
        cancellation_requested=None,
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
                    if self._is_cancellation_requested(cancellation_requested):
                        return
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
            if self._is_cancellation_requested(cancellation_requested):
                return
            display_title = " ".join(str(video_title).split())
            print(f"\n┌─ Video {index + 1}/{len(selected_videos)}")
            print(f"│ {display_title}")
            print("│")
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
                print("│  Video was not found; skipped")
                for language in selected_languages:
                    if self._is_cancellation_requested(cancellation_requested):
                        return
                    self._emit_finished(
                        progress_callback,
                        video_title,
                        language,
                        "skipped",
                        "video_not_found",
                    )
                print(
                    f"└─ Finished — 0/{len(selected_languages)} "
                    "localizations published"
                )
                continue

            source_language_code = getattr(
                target_video, "default_language_code", None
            )
            if not source_language_code:
                youtube.videos_skipped += len(selected_languages)
                print("│  Source language is not set on YouTube; skipped")
                for language in selected_languages:
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "source_language_missing",
                    )
                print(
                    f"└─ Finished — 0/{len(selected_languages)} "
                    "localizations published"
                )
                continue

            pending_localizations = []
            for language in selected_languages:
                if self._is_cancellation_requested(cancellation_requested):
                    break
                self._emit(
                    progress_callback,
                    type="item_started",
                    video=target_video.video_title,
                    language=language,
                    stage="preparing",
                )
                language_code = youtube.name_to_code.get(language.strip())
                if not language_code:
                    youtube.videos_skipped += 1
                    print(f"│  – {language}: unknown YouTube language; skipped")
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "unknown_language",
                    )
                    continue

                if language_code == source_language_code:
                    print(f"│  – {language}: source language; skipped")
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "source_language",
                    )
                    continue

                if language in target_video.language_names and not overwrite:
                    print(f"│  – {language}: already localized; skipped")
                    self._emit_finished(
                        progress_callback,
                        target_video.video_title,
                        language,
                        "skipped",
                        "already_localized",
                    )
                    continue

                translation, outcome, reason = self._translate(
                    provider,
                    target_video,
                    language,
                    language_code,
                    source_language_code,
                    progress_callback,
                )
                if translation is not None:
                    pending_localizations.append(translation)
                    continue

                if outcome != "succeeded":
                    youtube.videos_skipped += 1
                self._emit_finished(
                    progress_callback,
                    target_video.video_title,
                    language,
                    outcome,
                    reason,
                )

            if not pending_localizations:
                print(
                    f"└─ Finished — 0/{len(selected_languages)} "
                    "localizations published"
                )
                continue

            publishing_language = (
                pending_localizations[0]["language"]
                if len(pending_localizations) == 1
                else f"{len(pending_localizations)} languages"
            )
            self._emit_stage(
                progress_callback,
                target_video,
                publishing_language,
                "publishing",
            )
            publish_results = self._publish_video_localizations(
                target_video,
                pending_localizations,
                trim_checked,
            )
            published_any = False
            for localization, result in zip(
                pending_localizations, publish_results
            ):
                outcome = result["outcome"]
                if outcome == "succeeded":
                    published_any = True
                    current_languages = getattr(
                        target_video, "current_languages", []
                    )
                    language_code = localization["language_code"]
                    if language_code not in current_languages:
                        current_languages.append(language_code)
                    target_video.current_languages = current_languages
                    language_names = getattr(target_video, "language_names", [])
                    if localization["language"] not in language_names:
                        language_names.append(localization["language"])
                    target_video.language_names = language_names
                else:
                    youtube.videos_skipped += 1
                self._emit_finished(
                    progress_callback,
                    target_video.video_title,
                    localization["language"],
                    outcome,
                    result.get("reason"),
                    result.get("trimmed", False),
                )

            published_count = sum(
                result["outcome"] == "succeeded" for result in publish_results
            )
            print(
                f"└─ Finished — {published_count}/{len(selected_languages)} "
                "localizations published"
            )

            if published_any and self.delay:
                if not self._is_cancellation_requested(cancellation_requested):
                    time.sleep(self.delay)
            if youtube.error_code:
                return
            if self._is_cancellation_requested(cancellation_requested):
                return

    def _translate(
        self,
        provider,
        video,
        language,
        language_code,
        source_language_code,
        progress_callback=None,
    ):
        if not provider.is_available:
            print(
                f"│  – {language}: {provider.name} is not configured; skipped"
            )
            return None, "skipped", "provider_unavailable"

        try:
            if not provider.is_language_supported(language_code):
                print(f"│  – {language}: not supported by {provider.name}; skipped")
                return None, "skipped", "unsupported_language"

            self._emit_stage(progress_callback, video, language, "translating_title")
            translated_title = provider.translate_text(
                video.video_title, language_code, source_language_code
            )
            self._emit_stage(
                progress_callback, video, language, "translating_description"
            )
            translated_description = provider.translate_text(
                video.description, language_code, source_language_code
            )
        except TranslationError as exc:
            print(
                f"│  ✗ {language}: {provider.name} error — {exc}; skipped"
            )
            reason = (
                "google_monthly_limit"
                if isinstance(exc, MonthlyTranslationLimitError)
                else "translation_error"
            )
            return None, "failed", reason

        print(f"│  ✓ {language}: translated with {provider.name}")
        return (
            {
                "language_code": language_code,
                "language": language,
                "title": translated_title,
                "description": translated_description,
            },
            None,
            None,
        )

    def _publish_video_localizations(
        self,
        video,
        localizations,
        trim_checked,
    ):
        youtube = self.youtube_client
        if hasattr(youtube, "set_video_localizations"):
            return youtube.set_video_localizations(
                video.id,
                localizations,
                trim_checked,
                video.video_title,
            )

        results = []
        for localization in localizations:
            trimmed_before = youtube.videos_trimmed
            published = youtube.set_video_localization(
                video.id,
                localization["language_code"],
                localization["language"],
                localization["title"],
                localization["description"],
                trim_checked,
                video.video_title,
            )
            if published is False:
                outcome = "failed" if youtube.error_code else "skipped"
                reason = "youtube_error" if youtube.error_code else "text_too_long"
            else:
                outcome = "succeeded"
                reason = None
            results.append(
                {
                    "outcome": outcome,
                    "reason": reason,
                    "trimmed": youtube.videos_trimmed > trimmed_before,
                }
            )
            if youtube.error_code:
                break
        return results

    @staticmethod
    def _emit(progress_callback, **event):
        if progress_callback:
            progress_callback(event)

    @staticmethod
    def _is_cancellation_requested(cancellation_requested):
        return bool(cancellation_requested and cancellation_requested())

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
