import argparse
import logging
import os
import re
import sys
import threading
import time

import googleapiclient.errors
from flask import Flask, jsonify, redirect, render_template, request, url_for

from .localization import LocalizationService
from .progress import LocalizationProgressTracker
from .settings import VALID_TRANSLATION_PROVIDERS, load_settings
from .translators import DeepLTranslator, GoogleCloudTranslator
from .usage import GoogleUsageTracker
from .youtube_client import (
    LANGUAGE_FLAGS,
    YOUTUBE_DEFAULT_DAILY_QUOTA,
    YOUTUBE_LOCALIZATION_BATCH_QUOTA_COST,
    YouTubeClient,
)


# languages categories to use in Translation window
TIER_1_LANGUAGES = {
    "English",
    "Spanish",
    "Portuguese",
    "French",
    "German",
    "Japanese",
    "Korean",
    "Russian",
    "Arabic",
    "Hindi",
    "Chinese (Traditional)",
    "Chinese (Simplified)",
}
TIER_2_LANGUAGES = {
    "Bengali",
    "Czech",
    "Dutch",
    "Filipino",
    "Greek",
    "Hebrew",
    "Indonesian",
    "Italian",
    "Malay",
    "Persian",
    "Polish",
    "Romanian",
    "Swedish",
    "Thai",
    "Turkish",
    "Ukrainian",
    "Urdu",
    "Vietnamese",
}
TIER_3_LANGUAGES = {
    "Afrikaans",
    "Armenian",
    "Azerbaijani",
    "Bulgarian",
    "Burmese",
    "Catalan",
    "Croatian",
    "Danish",
    "Estonian",
    "Finnish",
    "Georgian",
    "Gujarati",
    "Hausa",
    "Hungarian",
    "Kazakh",
    "Kurdish",
    "Latvian",
    "Lithuanian",
    "Malayalam",
    "Marathi",
    "Mongolian",
    "Nepali",
    "Norwegian",
    "Pashto",
    "Punjabi",
    "Serbian",
    "Slovak",
    "Slovenian",
    "Swahili",
    "Tamil",
    "Telugu",
    "Uzbek",
}

LANGUAGE_PROVIDER_SUPPORT = {}


APP_BANNER_LINES = (
    ("__   _______.", "  _                    _ _"),
    (r"\ \ / /_   _|", r" | |    ___   ___ __ _| (_)_______ _ __"),
    (r" \ V /  | |", r"   | |   / _ \ / __/ _` | | |_  / _ \ '__|"),
    ("  | |   | |", "   | |__| (_) | (_| (_| | | |/ /  __/ |"),
    ("  |_|   |_|", r"   |_____\___/ \___\__,_|_|_/___\___|_|"),
)

YOUTUBE_RED = "\033[1;38;2;255;0;0m"
SUCCESS_GREEN = "\033[1;38;2;34;197;94m"
NOTICE_YELLOW = "\033[1;38;2;250;204;21m"
ANSI_RESET = "\033[0m"

RUSSIA_FLAG = ((255, 255, 255), (0, 57, 166), (213, 43, 30))
ITALY_FLAG = ((0, 146, 70), (255, 255, 255), (206, 43, 55))
GERMANY_FLAG = ((45, 45, 45), (221, 0, 0), (255, 206, 0))
FRANCE_FLAG = ((0, 85, 164), (255, 255, 255), (239, 65, 53))


def _colored_flag_row(colors):
    return "".join(
        f"\033[38;2;{red};{green};{blue}m██"
        for red, green, blue in colors
    ) + ANSI_RESET


# showing branded banner when starting the app
def _print_startup_banner():
    use_color = (
        sys.stdout.isatty()
        and os.getenv("TERM") != "dumb"
        and "NO_COLOR" not in os.environ
    )
    banner_width = max(
        len(youtube_part) + len(localizer_part)
        for youtube_part, localizer_part in APP_BANNER_LINES
    )
    print()
    if use_color:
        for line_index, (youtube_part, localizer_part) in enumerate(
            APP_BANNER_LINES
        ):
            if line_index == 2:
                left_flag = _colored_flag_row(RUSSIA_FLAG)
                right_flag = _colored_flag_row(GERMANY_FLAG)
            elif line_index == 4:
                left_flag = _colored_flag_row(ITALY_FLAG)
                right_flag = _colored_flag_row(FRANCE_FLAG)
            else:
                left_flag = right_flag = " " * 6

            line_width = len(youtube_part) + len(localizer_part)
            print(
                f"{left_flag}  {YOUTUBE_RED}{youtube_part}{ANSI_RESET}"
                f"{localizer_part}{' ' * (banner_width - line_width)}  "
                f"{right_flag}"
            )
    else:
        for youtube_part, localizer_part in APP_BANNER_LINES:
            print(f"{youtube_part}{localizer_part}")
    signature_indent = " " * 8 if use_color else ""
    print(
        f"{signature_indent}"
        f"{'by 🐸 Vagabondity Walks'.rjust(banner_width)}"
    )
    print("\nStarting application…\n")


def _terminal_link(label, url):
    """Return an OSC 8 hyperlink when output is an interactive terminal."""
    if not sys.stdout.isatty() or os.getenv("TERM") == "dumb":
        return label
    return f"\033]8;;{url}\033\\\033[1;36m{label}\033[0m\033]8;;\033\\"

# button with a link to the app
def _print_application_link(url):
    label = f"▶  OPEN YT LOCALIZER: {url}"
    border = "═" * (len(label) + 2)
    print(f"\n╔{border}╗")
    print(f"║ {_terminal_link(label, url)} ║")
    print(f"╚{border}╝")
    print("Click the link above or copy the address into your browser.\n")


def _print_technical_info_notice():
    title = "🛠️  TECHNICAL SERVER INFORMATION"
    messages = (
        "Everything below is application and server activity.",
        "No action is required — keep this terminal open and use the app.",
        "If something goes wrong, include these logs in your issue report.",
    )
    stop_message = "Press CTRL+C to stop the application."
    content_width = max(
        len(title), len(stop_message), *(len(message) for message in messages)
    )
    width = content_width + 2
    use_color = (
        sys.stdout.isatty()
        and os.getenv("TERM") != "dumb"
        and "NO_COLOR" not in os.environ
    )
    print(f"┌{'─' * width}┐")
    print(f"│ {title.center(content_width)}  │")
    print(f"├{'─' * width}┤")
    for message in messages:
        print(f"│ {message.ljust(content_width)} │")
    print(f"├{'─' * width}┤")
    if use_color:
        print(
            f"│ {NOTICE_YELLOW}{stop_message.center(content_width)}"
            f"{ANSI_RESET} │"
        )
    else:
        print(f"│ {stop_message.center(content_width)} │")
    print(f"└{'─' * width}┘")


# show info about the app when it starts
def _print_startup_summary(app, url, startup_duration):
    youtube = app.extensions["youtube_client"]
    localizer = app.extensions["localization_service"]
    usage_tracker = app.extensions["google_usage_tracker"]

    if youtube.error_code:
        youtube_status = (
            "limited — daily quota exceeded"
            if youtube.error_code == "quotaExceeded"
            else f"unavailable — {youtube.error_code}"
        )
    else:
        channel_name = " ".join(youtube.channel_name.split()) or "channel connected"
        youtube_status = f"ready — {channel_name}, {youtube.total_video_count:,} videos"

    google = localizer.google_translator
    if not google.is_available:
        google_status = "not configured"
    elif google.supported_language_count:
        google_status = (
            f"ready ({google.supported_language_count} supported languages)"
        )
    else:
        google_status = "configured (supported languages unavailable)"

    deepl_status = (
        "configured (connection not checked)"
        if localizer.deepl_translator.is_available
        else "not configured"
    )

    usage = usage_tracker.get_google_usage()
    if usage["status"] == "ready":
        protection = "enabled" if usage["safety_limit_enabled"] else "disabled"
        usage_status = (
            f"{protection} ({usage['used']:,} / {usage['limit']:,} characters)"
        )
    else:
        usage_status = f"unavailable — {usage['message']}"

    default_provider = {
        "deepl": "DeepL",
        "google": "Google Cloud",
    }[app.config["DEFAULT_TRANSLATION_PROVIDER"]]

    print("Startup status:")
    print("  Configuration: loaded")
    print(f"  YouTube: {youtube_status}")
    print("  Translation providers:")
    print(f"    Google Cloud: {google_status}")
    print(f"    DeepL: {deepl_status}")
    print(f"  Default provider: {default_provider}")
    print(f"  Google usage protection: {usage_status}")
    print(f"  Startup time: {startup_duration:.1f}s")
    ready_message = "✓ Application is ready to use"
    if (
        sys.stdout.isatty()
        and os.getenv("TERM") != "dumb"
        and "NO_COLOR" not in os.environ
    ):
        print(f"\n{SUCCESS_GREEN}{ready_message}{ANSI_RESET}")
    else:
        print(f"\n{ready_message}")
    _print_application_link(url)


class _RequestLogFilter(logging.Filter):
    """Hide successful polling and compact Werkzeug request messages."""

    _poll_request = re.compile(
        r'"GET /localizations/[0-9a-f]{32} HTTP/[^"]+" (?:200|304) '
    )
    _request_log = re.compile(
        r"^\S+ - - \["
        r"(?P<day>\d{2})/(?P<month>[A-Z][a-z]{2})/(?P<year>\d{4}) "
        r"(?P<time>\d{2}:\d{2}:\d{2})\] (?P<request>.*)$"
    )
    _request_details = re.compile(
        r'^"(?P<request>.*) HTTP/[0-9.]+'
        r'(?P<reset>\x1b\[[0-9;]*m)?" '
        r'(?P<status>\d{3})(?: (?:\d+|-))?$'
    )
    _months = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    _ansi_codes = re.compile(r"\x1b\[[0-9;]*m")

    def filter(self, record):
        message = record.getMessage()
        if self._ansi_codes.sub("", message).strip() == "Press CTRL+C to quit":
            return False
        if self._poll_request.search(message):
            return False

        match = self._request_log.match(message)
        if match and match["month"] in self._months:
            short_year = match["year"][-2:]
            request_details = match["request"]
            details_match = self._request_details.match(request_details)
            if details_match:
                ansi_reset = details_match["reset"] or ""
                request_details = (
                    f"{details_match['request']}{ansi_reset} "
                    f"{details_match['status']}"
                )
            record.msg = (
                f"[{match['day']}.{self._months[match['month']]}.{short_year} "
                f"{match['time']}] {request_details}"
            )
            record.args = ()
        return True


def _configure_request_logging():
    werkzeug_logger = logging.getLogger("werkzeug")
    if not any(
        isinstance(log_filter, _RequestLogFilter)
        for log_filter in werkzeug_logger.filters
    ):
        werkzeug_logger.addFilter(_RequestLogFilter())


def build_language_tiers(language_names):
    """Group display languages without changing their configured order."""
    tier_definitions = (
        (
            "tier-1",
            "🌍 Global",
            "Largest global audiences",
            TIER_1_LANGUAGES,
            True,
        ),
        (
            "tier-2",
            "⭐ Major",
            "Major national & online audiences",
            TIER_2_LANGUAGES,
            False,
        ),
        (
            "tier-3",
            "📍 Regional",
            "Significant regional audiences",
            TIER_3_LANGUAGES,
            False,
        ),
    )
    tiers = []
    for tier_id, label, description, included_languages, expanded in tier_definitions:
        languages = [name for name in language_names if name in included_languages]
        if languages:
            tiers.append(
                {
                    "id": tier_id,
                    "label": label,
                    "description": description,
                    "languages": languages,
                    "expanded": expanded,
                }
            )
    return tiers


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
    app.config["DEFAULT_TRANSLATION_PROVIDER"] = settings.default_translation_provider
    _configure_request_logging()

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
                    if youtube.error_code == "quotaExceeded":
                        return jsonify(
                            {
                                "error": (
                                    "YouTube quota is unavailable until the daily reset."
                                )
                            }
                        ), 429
                    youtube.error_code = ""
                    translation_provider = payload.get("translation_provider")
                    if translation_provider not in VALID_TRANSLATION_PROVIDERS:
                        return jsonify({"error": "Select a translation provider."}), 400
                    localizer.localize_videos(
                        payload["selected_videos"],
                        payload["selected_languages"],
                        payload.get("overwrite", False),
                        translation_provider,
                        payload.get("trim_checked", False),
                        selected_video_ids=payload.get("selected_video_ids"),
                    )
                    return jsonify({"status": "ok"})

                return jsonify({"error": "Unsupported request"}), 400

            youtube.set_video_filter(request.args.get("video_filter", "all"))
            requested_page = request.args.get("page", 1, type=int)
            if request.args.get("retry_youtube") == "1":
                youtube.refresh_video_cache()
                return redirect(
                    url_for(
                        "home",
                        page=requested_page,
                        video_filter=youtube.video_filter,
                    )
                )

            if youtube.error_code == "quotaExceeded" and not youtube.video_inventory:
                page = 1
                youtube.page_videos = []
                youtube.all_videos_cache = []
            else:
                page = youtube.set_video_page(requested_page)
            populate_localization_language_names(youtube)
            youtube_quota_exceeded = youtube.error_code == "quotaExceeded"
            display_num_pages = (
                2
                if youtube_quota_exceeded and not youtube.video_inventory
                else youtube.num_pages + 1
            )

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
                language_tiers=build_language_tiers(
                    youtube.language_names_in_display_order
                ),
                language_flags=LANGUAGE_FLAGS,
                language_provider_support=LANGUAGE_PROVIDER_SUPPORT,
                channel_thumbnail=youtube.channel_thumbnail,
                channel_name=youtube.channel_name,
                num_pages=display_num_pages,
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
                youtube_default_daily_quota=YOUTUBE_DEFAULT_DAILY_QUOTA,
                youtube_localization_batch_quota_cost=(
                    YOUTUBE_LOCALIZATION_BATCH_QUOTA_COST
                ),
                youtube_quota_exceeded=youtube_quota_exceeded,
                has_cached_videos=bool(youtube.video_inventory),
            )
        except (googleapiclient.errors.HttpError, IndexError, KeyError) as exc:
            print(f"Error in home route: {exc}")
            return render_template(
                "quota-error.html",
                youtube_default_daily_quota=YOUTUBE_DEFAULT_DAILY_QUOTA,
            )

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
        if youtube.error_code == "quotaExceeded":
            return jsonify(
                {"error": "YouTube quota is unavailable until the daily reset."}
            ), 429

        provider = payload.get("translation_provider")
        if provider not in VALID_TRANSLATION_PROVIDERS:
            return jsonify({"error": "Select a translation provider."}), 400
        job_id, job = progress_tracker.start(
            len(selected_videos), len(selected_languages), provider
        )
        if job_id is None:
            return jsonify({"error": "A localization run is already active.", "job": job}), 409

        run_label = job_id[:8]
        started_at = time.monotonic()
        provider_label = {
            "deepl": "DeepL",
            "google": "Google Cloud Translation",
        }[provider]
        print(
            f"\nLocalization [{run_label}] started: {provider_label}, "
            f"{job['video_count']} video(s) × {job['language_count']} language(s) "
            f"= {job['total']} localization(s)"
        )

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
                progress_tracker.finish(job_id, youtube.error_code)
                finished_job = progress_tracker.get(job_id)
                duration = time.monotonic() - started_at
                status = "stopped" if youtube.error_code else "completed"
                print(
                    f"Localization [{run_label}] {status} in {duration:.1f}s: "
                    f"{finished_job['processed']}/{finished_job['total']} processed, "
                    f"{finished_job['succeeded']} succeeded, "
                    f"{finished_job['skipped']} skipped, "
                    f"{finished_job['failed']} failed"
                    + (f"; reason: {youtube.error_code}" if youtube.error_code else "")
                    + "\n"
                )
            except Exception as exc:
                progress_tracker.fail(job_id, exc)
                duration = time.monotonic() - started_at
                print(
                    f"Localization [{run_label}] failed after {duration:.1f}s: {exc}\n"
                )

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
        google_usage = (
            usage_tracker.get_google_usage()
            if localizer.google_translator.is_available
            else {
                "status": "not_configured",
                "message": "Not configured",
            }
        )
        return jsonify(
            {
                "google": google_usage,
                "deepl": localizer.deepl_translator.get_usage(),
            }
        )

    @app.route("/providers/google/protection", methods=["POST"])
    def set_google_protection():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or type(payload.get("enabled")) is not bool:
            return jsonify({"error": "Protection must be true or false"}), 400
        try:
            usage_tracker.set_safety_limit_enabled(payload["enabled"])
        except (OSError, ValueError):
            return jsonify({"error": "Could not save protection settings. Check the local usage file."}), 500
        return jsonify({"google": usage_tracker.get_google_usage()})

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
            if (
                payload.get("refresh")
                and selected_videos
                and youtube.error_code != "quotaExceeded"
            ):
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
                    "youtube_quota_exceeded": (
                        youtube.error_code == "quotaExceeded"
                    ),
                }
            )
        except (AttributeError, TypeError, ValueError) as exc:
            print(f"Error reading selected languages: {exc}")
            return jsonify({"current_languages": []}), 400

    @app.route("/providers/<provider_name>/test", methods=["POST"])
    def test_provider_connection(provider_name):
        """Run a tiny real translation through one configured provider."""
        if not request.is_json:
            return jsonify({"error": "JSON request required"}), 415
        providers = {
            "google": localizer.google_translator,
            "deepl": localizer.deepl_translator,
        }
        provider = providers.get(provider_name)
        if provider is None:
            return jsonify({"error": "Unknown translation provider"}), 404
        return jsonify(provider.test_connection())

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
    host = "127.0.0.1"
    url = f"http://{host}:{args.port}"
    _print_startup_banner()
    started_at = time.monotonic()
    app = create_app()
    youtube = app.extensions["youtube_client"]
    if not youtube.error_code:
        print("Loading YouTube video library…")
        youtube.set_video_page(1)
        if not youtube.error_code:
            print(f"Video library loaded — {len(youtube.video_inventory):,} videos.\n")
    _print_startup_summary(app, url, time.monotonic() - started_at)
    _print_technical_info_notice()
    app.run(debug=debug, host=host, port=args.port)


if __name__ == "__main__":
    main()
