import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SETTINGS_PATH = Path("config/settings.toml")
VALID_TRANSLATION_PROVIDERS = {"google", "deepl"}


@dataclass(frozen=True)
class AppSettings:
    """Local paths and secrets used by the application."""

    youtube_oauth_client_file: str
    youtube_token_file: str
    google_credentials_file: str
    deepl_api_key: str | None
    default_translation_provider: str


def load_settings(settings_path=None):
    """Load local TOML settings."""
    path = Path(
        settings_path
        or os.getenv("VYL_SETTINGS_FILE", str(DEFAULT_SETTINGS_PATH))
    ).expanduser()
    data = {}
    if path.exists():
        with path.open("rb") as settings_file:
            data = tomllib.load(settings_file)

    youtube = data.get("youtube", {})
    google = data.get("google", {})
    deepl = data.get("deepl", {})
    translation = data.get("translation", {})

    default_provider = str(
        translation.get("default_provider", "deepl")
    ).strip().lower()
    if default_provider not in VALID_TRANSLATION_PROVIDERS:
        raise ValueError(
            "translation.default_provider must be 'deepl' or 'google'"
        )

    deepl_api_key = str(deepl.get("api_key", "")).strip()

    return AppSettings(
        youtube_oauth_client_file=str(
            youtube.get(
                "oauth_client_file",
                "config/account_client_secrets_main.json",
            )
        ),
        youtube_token_file=str(youtube.get("token_file", "token.pickle")),
        google_credentials_file=str(
            google.get("credentials_file", "config/translate_key.json")
        ),
        deepl_api_key=deepl_api_key or None,
        default_translation_provider=default_provider,
    )
