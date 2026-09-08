import deepl.exceptions
from deepl import Translator as DeepLClient

from .base import TranslationError


# YouTube uses a few generic or legacy language codes that DeepL expects in a
# more specific form. Portuguese defaults to Brazilian Portuguese because it is
# the largest Portuguese-speaking YouTube market.
DEEPL_TARGET_LANGUAGE_CODES = {
    "en": "en-us",
    "fil": "tl",
    "iw": "he",
    "ku": "kmr",
    "no": "nb",
    "pt": "pt-br",
    "zh-CN": "zh-hans",
    "zh-TW": "zh-hant",
}

DEEPL_SOURCE_LANGUAGE_CODES = {
    "iw": "he",
    "no": "nb",
    "zh-CN": "zh",
    "zh-TW": "zh",
}


class DeepLTranslator:
    """Translate text through DeepL without falling back to another provider."""

    name = "DeepL"

    def __init__(self, api_key=None):
        self._client = None
        self._source_language_codes = None
        self._target_language_codes = None
        self._language_capability_error = None

        if not api_key:
            print("DeepL is not configured")
            return

        try:
            self._client = DeepLClient(api_key)
        except Exception as exc:
            print(f"Error initializing DeepL: {exc}")

    @property
    def is_available(self):
        return self._client is not None

    @staticmethod
    def _normalize_language_code(language_code):
        return DEEPL_TARGET_LANGUAGE_CODES.get(
            language_code, language_code
        ).lower()

    @staticmethod
    def _normalize_source_language_code(language_code):
        return DEEPL_SOURCE_LANGUAGE_CODES.get(
            language_code, language_code
        ).upper()

    def is_language_supported(self, language_code):
        """Return whether DeepL advertises the language as a target."""
        return self.is_target_language_supported(language_code) is True

    def _load_supported_languages(self):
        """Load source and target capabilities without translating text."""
        if (
            self._source_language_codes is not None
            and not self._language_capability_error
        ):
            return
        try:
            # deepl-python's public language methods still use the deprecated
            # v2 endpoint, so use its configured HTTP client for the v3 call.
            status, content, languages = self._client._api_call(
                "v3/languages",
                method="GET",
                params={"resource": "translate_text"},
            )
            self._client._raise_for_status(status, content, languages)
            if not isinstance(languages, list):
                raise ValueError("DeepL returned an invalid language list")

            self._source_language_codes = {
                language["lang"].upper()
                for language in languages
                if language.get("usable_as_source") is True
            }
            self._target_language_codes = {
                language["lang"].lower()
                for language in languages
                if language.get("usable_as_target") is True
            }
            self._language_capability_error = None
        except Exception as exc:
            self._source_language_codes = set()
            self._target_language_codes = set()
            self._language_capability_error = str(exc)
            print(f"Error loading DeepL supported languages: {exc}")

    def is_source_language_supported(self, language_code):
        if not self.is_available:
            return False
        self._load_supported_languages()
        if self._language_capability_error:
            return None
        source_language = self._normalize_source_language_code(language_code)
        return source_language in self._source_language_codes

    def is_target_language_supported(self, language_code):
        if not self.is_available:
            return False
        self._load_supported_languages()
        if self._language_capability_error:
            return None
        target_language = self._normalize_language_code(language_code)
        return target_language in self._target_language_codes

    def supports_translation(self, source_language, target_language):
        source_supported = self.is_source_language_supported(source_language)
        target_supported = self.is_target_language_supported(target_language)
        if source_supported is None or target_supported is None:
            return None
        return source_supported and target_supported

    def test_connection(self):
        """Verify the API key with a tiny real translation request."""
        if not self.is_available:
            return {
                "ok": False,
                "status": "not_configured",
                "message": "Not configured",
            }

        try:
            self.translate_text("hi", "de", "en")
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

    def get_usage(self):
        """Return current DeepL account character usage and limit."""
        if not self.is_available:
            return {
                "status": "not_configured",
                "message": "Not configured",
            }

        try:
            usage = self._client.get_usage()
            character_usage = usage.character
            if not character_usage.valid:
                return {
                    "status": "unavailable",
                    "message": "DeepL did not return a character limit.",
                }
            used = character_usage.count
            limit = character_usage.limit
            return {
                "status": "ready",
                "used": used,
                "limit": limit,
                "remaining": max(0, limit - used),
                "message": "Live usage from your DeepL account.",
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Could not retrieve DeepL usage: {exc}",
            }

    def translate_text(self, text, target_language, source_language):
        if not text or not text.strip():
            return text
        if not self.is_available:
            raise TranslationError("DeepL is not configured")

        target_language = self._normalize_language_code(target_language)
        source_language = self._normalize_source_language_code(source_language)
        try:
            return self._client.translate_text(
                text,
                source_lang=source_language,
                target_lang=target_language,
            ).text
        except deepl.exceptions.QuotaExceededException as exc:
            raise TranslationError("DeepL quota exceeded") from exc
        except Exception as exc:
            raise TranslationError(
                f"DeepL failed to translate to '{target_language}': {exc}"
            ) from exc
