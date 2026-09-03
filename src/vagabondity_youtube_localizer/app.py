import argparse
import os
import threading

import googleapiclient.errors
from flask import Flask, jsonify, redirect, render_template, request, url_for

from .localization import LocalizationService
from .progress import LocalizationProgressTracker
from .settings import load_settings
from .translators import DeepLTranslator, GoogleCloudTranslator
from .usage import GoogleUsageTracker
from .youtube_client import LANGUAGE_FLAGS, YouTubeClient


def create_app(
    youtube_client=None,
    localization_service=None,
    usage_tracker=None,
    progress_tracker=None,
):
    """Create and configure the local Flask application."""
    settings = load_settings()
    usage_tracker = usage_tracker or GoogleUsageTracker()

    app = Flask(__name__)
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    youtube = youtube_client or YouTubeClient(
        oauth_client_file=settings.youtube_oauth_client_file,
        token_file=settings.youtube_token_file,
    )
    localizer = localization_service or LocalizationService(
        youtube_client=youtube,
        google_translator=GoogleCloudTranslator(
            credentials_path=settings.google_credentials_file,
            usage_tracker=usage_tracker,
        ),
        deepl_translator=DeepLTranslator(api_key=settings.deepl_api_key),
    )
    progress_tracker = progress_tracker or LocalizationProgressTracker()

    # Expose dependencies for diagnostics and isolated tests.
    app.extensions["youtube_client"] = youtube
    app.extensions["localization_service"] = localizer
    app.extensions["google_usage_tracker"] = usage_tracker
    app.extensions["localization_progress_tracker"] = progress_tracker

    @app.route("/", methods=["GET", "POST"])
    def home():
        """Render videos and handle page-size or localization requests."""
        try:
            if request.method == "POST":
                payload = request.get_json(silent=True) or {}
                youtube.error_code = ""

                if "per_page" in payload:
                    per_page = int(payload["per_page"])
                    youtube.per_page_option_index = int(
                        payload.get("per_page_option_index", 0)
                    )
                    youtube.results_per_page = (
                        per_page if per_page < youtube.total_video_count else -1
                    )
                    return redirect(
                        url_for(
                            "home",
                            page=1,
                            video_filter=youtube.video_filter,
                        )
                    )

                if "selected_videos" in payload and "selected_languages" in payload:
                    translation_provider = payload.get("translation_provider")
                    if translation_provider is None:
                        translation_provider = (
                            "deepl" if payload.get("use_deepL") else "google"
                        )
                    localizer.localize_videos(
                        payload["selected_videos"],
                        payload["selected_languages"],
                        payload.get("overwrite", False),
                        translation_provider,
                        payload.get("trim_checked", False),
                        selected_video_ids=payload.get("selected_video_ids"),
                    )
                    youtube.clear_video_cache()
                    return jsonify({"status": "ok"})

                return jsonify({"error": "Unsupported request"}), 400

            youtube.set_video_filter(request.args.get("video_filter", "all"))
            page = youtube.set_video_page(request.args.get("page", 1, type=int))
            populate_localization_language_names(youtube)

            if youtube.error_code == "quotaExceeded":
                return render_template("quota-error.html")

            all_video_titles = (
                [video.video_title for video in youtube.all_videos_cache]
                if youtube.results_per_page == -1
                else []
            )
            all_video_ids = (
                [video.id for video in youtube.all_videos_cache]
                if youtube.results_per_page == -1
                else []
            )

            return render_template(
                "home.html",
                page_videos=youtube.page_videos,
                all_videos=all_video_titles,
                all_video_ids=all_video_ids,
                all_language_names=youtube.language_names_in_display_order,
                language_flags=LANGUAGE_FLAGS,
                channel_thumbnail=youtube.channel_thumbnail,
                channel_name=youtube.channel_name,
                num_pages=youtube.num_pages + 1,
                current_page=page,
                error_str=youtube.error_code,
                per_page_index=youtube.per_page_option_index,
                trimmed=youtube.videos_trimmed,
                skipped=youtube.videos_skipped,
                total_videos=youtube.total_video_count,
                filtered_video_count=youtube.filtered_video_count,
                video_filter=youtube.video_filter,
                video_filter_counts=youtube.video_filter_counts,
                default_translation_provider=settings.default_translation_provider,
                provider_availability={
                    "google": localizer.google_translator.is_available,
                    "deepl": localizer.deepl_translator.is_available,
                },
            )
        except (googleapiclient.errors.HttpError, IndexError, KeyError) as exc:
            print(f"Error in home route: {exc}")
            return render_template("quota-error.html")

    @app.route("/error/", methods=["GET"])
    def get_translation_status():
        """Return the result of the most recent localization operation."""
        return jsonify(
            {
                "error": youtube.error_code,
                "trimmed": youtube.videos_trimmed,
                "skipped": youtube.videos_skipped,
            }
        )

    @app.route("/localizations", methods=["POST"])
    def start_localization():
        """Start a localization run and return an id for live progress polling."""
        payload = request.get_json(silent=True) or {}
        selected_videos = payload.get("selected_videos", [])
        selected_languages = payload.get("selected_languages", [])
        if not selected_videos or not selected_languages:
            return jsonify({"error": "Select at least one video and language."}), 400

        provider = payload.get("translation_provider")
        job_id, job = progress_tracker.start(
            len(selected_videos), len(selected_languages), provider
        )
        if job_id is None:
            return jsonify({"error": "A localization run is already active.", "job": job}), 409

        def run_localization():
            try:
                youtube.error_code = ""
                localizer.localize_videos(
                    selected_videos,
                    selected_languages,
                    payload.get("overwrite", False),
                    provider,
                    payload.get("trim_checked", False),
                    selected_video_ids=payload.get("selected_video_ids"),
                    progress_callback=lambda event: progress_tracker.update(
                        job_id, event
                    ),
                )
                youtube.clear_video_cache()
                progress_tracker.finish(job_id, youtube.error_code)
            except Exception as exc:
                print(f"Unexpected localization error: {exc}")
                progress_tracker.fail(job_id, exc)

        threading.Thread(target=run_localization, daemon=True).start()
        return jsonify({"job_id": job_id, "job": job}), 202

    @app.route("/localizations/<job_id>", methods=["GET"])
    def get_localization_progress(job_id):
        """Return a snapshot of a running or recently finished localization run."""
        job = progress_tracker.get(job_id)
        if job is None:
            return jsonify({"error": "Localization run not found."}), 404
        return jsonify(job)

    @app.route("/localizations/active", methods=["GET"])
    def get_active_localization():
        """Let a reloaded page reconnect to the active localization run."""
        return jsonify({"job": progress_tracker.get_active()})

    @app.route("/providers/usage", methods=["POST"])
    def get_provider_usage():
        """Return provider usage without exposing configured credentials."""
        return jsonify(
            {
                "google": usage_tracker.get_google_usage(),
                "deepl": localizer.deepl_translator.get_usage(),
            }
        )

    @app.route("/languages", methods=["POST"])
    def get_common_localization_languages():
        """Return localization and source-language state for selected videos."""
        try:
            payload = request.get_json(silent=True) or {}
            selected_video_names = {
                normalize_title(name) for name in payload.get("vidNames", [])
            }
            selected_video_ids = {
                str(video_id) for video_id in payload.get("videoIds", [])
            }
            videos_to_check = (
                youtube.all_videos_cache
                if youtube.results_per_page == -1
                else youtube.page_videos
            )

            selected_videos = [
                video
                for video in videos_to_check
                if (
                    str(video.id) in selected_video_ids
                    if selected_video_ids
                    else normalize_title(video.video_title) in selected_video_names
                )
            ]
            languages_refreshed = False
            if payload.get("refresh") and selected_videos:
                languages_refreshed = youtube.refresh_video_language_metadata(
                    selected_videos
                )
                populate_video_language_names(youtube, selected_videos)

            language_states = {}
            for video in selected_videos:
                localized_names = set(getattr(video, "language_names", []))
                localized_names.update(
                    filter(
                        None,
                        (
                            youtube.code_to_name.get(code)
                            for code in getattr(video, "current_languages", [])
                        ),
                    )
                )
                for language in localized_names:
                    state = language_states.setdefault(
                        language, {"localized_count": 0, "default_count": 0}
                    )
                    state["localized_count"] += 1

                default_language = getattr(video, "default_language_name", None)
                if not default_language:
                    default_language = youtube.code_to_name.get(
                        getattr(video, "default_language_code", None)
                    )
                if default_language:
                    state = language_states.setdefault(
                        default_language,
                        {"localized_count": 0, "default_count": 0},
                    )
                    state["default_count"] += 1

            common_languages = [
                language
                for language, state in language_states.items()
                if state["localized_count"] == len(selected_videos)
            ]
            return jsonify(
                {
                    "current_languages": common_languages,
                    "language_states": language_states,
                    "selected_count": len(selected_videos),
                    "refreshed": languages_refreshed,
                }
            )
        except (AttributeError, TypeError, ValueError) as exc:
            print(f"Error reading selected languages: {exc}")
            return jsonify({"current_languages": []}), 400

    @app.route("/providers/test", methods=["POST"])
    def test_provider_connections():
        """Run a tiny real translation through each configured provider."""
        if not request.is_json:
            return jsonify({"error": "JSON request required"}), 415
        return jsonify(
            {
                "google": localizer.google_translator.test_connection(),
                "deepl": localizer.deepl_translator.test_connection(),
            }
        )

    return app


def populate_localization_language_names(youtube_client):
    """Populate display names for the currently loaded video localizations."""
    populate_video_language_names(youtube_client, youtube_client.page_videos)


def populate_video_language_names(youtube_client, videos):
    """Populate display names for localization and source language codes."""
    for video in videos:
        video.language_names = []
        for language_code in video.current_languages:
            language_name = youtube_client.code_to_name.get(language_code)
            if language_name and language_name not in video.language_names:
                video.language_names.append(language_name)
        video.default_language_name = youtube_client.code_to_name.get(
            getattr(video, "default_language_code", None)
        )


def normalize_title(title):
    """Match titles using the behavior expected by the existing browser UI."""
    return str(title).replace(" ", "")


def main():
    """Run the application on the local machine only."""
    parser = argparse.ArgumentParser(
        description="Run Vagabondity YouTube Localizer on this computer."
    )
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    debug = args.debug or os.getenv("FLASK_DEBUG", "").lower() in {
        "1",
        "true",
        "yes",
    }
    create_app().run(debug=debug, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
