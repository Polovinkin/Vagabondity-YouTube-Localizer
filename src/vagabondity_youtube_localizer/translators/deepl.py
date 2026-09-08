import deepl.exceptions
from deepl import Translator as DeepLClient

from .base import TranslationError


# YouTube uses a few generic or legacy language codes that DeepL expects in a
# more specific form. Portuguese defaults to Brazilian Portuguese because it is
# the largest Portuguese-speaking YouTube market.
DEEPL_TARGET_LANGUAGE_CODES = {
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
        """Accept configured languages and let the translation endpoint validate them."""
        return bool(self._normalize_language_code(language_code))

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
