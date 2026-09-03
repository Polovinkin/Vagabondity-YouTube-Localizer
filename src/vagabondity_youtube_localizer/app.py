import argparse
import os

import googleapiclient.errors
from flask import Flask, jsonify, redirect, render_template, request, url_for

from .localization import LocalizationService
from .settings import load_settings
from .translators import DeepLTranslator, GoogleCloudTranslator
from .usage import GoogleUsageTracker
from .youtube_client import LANGUAGE_FLAGS, YouTubeClient


def create_app(youtube_client=None, localization_service=None, usage_tracker=None):
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

    # Expose dependencies for diagnostics and isolated tests.
    app.extensions["youtube_client"] = youtube
    app.extensions["localization_service"] = localizer
    app.extensions["google_usage_tracker"] = usage_tracker

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

            return render_template(
                "home.html",
                page_videos=youtube.page_videos,
                all_videos=all_video_titles,
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
        """Return localizations shared by every selected video."""
        try:
            payload = request.get_json(silent=True) or {}
            selected_video_names = {
                normalize_title(name) for name in payload.get("vidNames", [])
            }
            expected_count = int(payload.get("num", 0))
            language_counts = {}
            videos_to_check = (
                youtube.all_videos_cache
                if youtube.results_per_page == -1
                else youtube.page_videos
            )

            for video in videos_to_check:
                if normalize_title(video.video_title) not in selected_video_names:
                    continue
                for language in video.language_names:
                    language_counts[language] = language_counts.get(language, 0) + 1

            common_languages = [
                language
                for language, count in language_counts.items()
                if count == expected_count
            ]
            return jsonify({"current_languages": common_languages})
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
    for video in youtube_client.page_videos:
        video.language_names = []
        for language_code in video.current_languages:
            language_name = youtube_client.code_to_name.get(language_code)
            if language_name and language_name not in video.language_names:
                video.language_names.append(language_name)


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
