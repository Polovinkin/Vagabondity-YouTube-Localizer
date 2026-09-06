import os

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import translate_v2 as translate
from google.oauth2 import service_account

from .base import MonthlyTranslationLimitError, TranslationError
from ..usage import GoogleUsageLimitError, GoogleUsageTracker


class GoogleCloudTranslator:
    """Small wrapper around the Google Cloud Translation v2 client."""

    name = "Google Cloud Translation"

    def __init__(self, credentials_path="config/translate_key.json", usage_tracker=None):
        self._credentials_path = credentials_path
        self._usage_tracker = usage_tracker if usage_tracker is not None else GoogleUsageTracker()
        self._client = None
        self._supported_language_codes = set()

        self._initialize_client()
        if self.is_available:
            self._load_supported_languages()

    @property
    def is_available(self):
        """Return whether a Google Cloud Translation client is configured."""
        return self._client is not None

    def _initialize_client(self):
        """Initialize the client from a local key or default credentials."""
        try:
            if os.path.exists(self._credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    self._credentials_path
                )
                self._client = translate.Client(credentials=credentials)
                print("Google Cloud Translation API initialized successfully")
                return

            print(
                "Warning: Google Cloud Translation credentials file not found at "
                f"{self._credentials_path}"
            )
            try:
                self._client = translate.Client()
                print("Using default Google Cloud credentials")
            except DefaultCredentialsError:
                print("Google Cloud Translation is not configured")
        except Exception as exc:
            print(f"Error initializing Google Cloud Translation: {exc}")
            self._client = None

    def _load_supported_languages(self):
        """Load the target language codes supported by the configured client."""
        try:
            languages = self._client.get_languages()
            self._supported_language_codes = {
                language["language"].lower()
                for language in languages
                if language.get("language")
            }
            print(
                "Loaded "
                f"{len(self._supported_language_codes)} supported languages from "
                "Google Cloud Translation"
            )
        except Exception as exc:
            print(f"Error loading Google Cloud Translation languages: {exc}")
            self._supported_language_codes = set()

    def is_language_supported(self, language_code):
        """Return whether Google Cloud supports a target language code."""
        return language_code.lower() in self._supported_language_codes

    def test_connection(self):
        """Verify credentials with a tiny real translation request."""
        if not self.is_available:
            return {
                "ok": False,
                "status": "not_configured",
                "message": "Not configured",
            }

        try:
            self.translate_text("hi", "de")
            return {
                "ok": True,
                "status": "connected",
                "message": "Connected and ready",
            }
        except TranslationError as exc:
            return {
                "ok": False,
                "status": "error",
                "message": str(exc),
            }

    def translate_text(self, text, target_language):
        """Translate English text or raise when the request cannot be completed."""
        if not text or not text.strip():
            return text

        if not self.is_available:
            raise TranslationError(
                "Google Cloud Translation is not configured"
            )

        if isinstance(text, bytes):
            text = text.decode("utf-8")

        try:
            self._usage_tracker.record_google_characters(len(text))
            result = self._client.translate(
                text,
                format_="text",
                source_language="en",
                target_language=target_language,
            )
            translated_text = result.get("translatedText")
            if translated_text is None:
                raise TranslationError(
                    "Google Cloud returned no translated text"
                )

            print(f"Google Cloud completed translation to '{target_language}'")
            return translated_text
        except GoogleUsageLimitError as exc:
            raise MonthlyTranslationLimitError(str(exc)) from exc
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(
                f"Google Cloud failed to translate to '{target_language}': {exc}"
            ) from exc
