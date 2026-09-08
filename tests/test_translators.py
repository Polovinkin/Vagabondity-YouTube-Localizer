import unittest
from unittest.mock import Mock

from vagabondity_youtube_localizer.translators import TranslationError
from vagabondity_youtube_localizer.translators.deepl import DeepLTranslator
from vagabondity_youtube_localizer.translators.google_cloud import (
    GoogleCloudTranslator,
)


class TranslatorTests(unittest.TestCase):
    def test_deepl_normalizes_youtube_language_codes(self):
        self.assertEqual(DeepLTranslator._normalize_language_code("en"), "en-us")
        self.assertEqual(DeepLTranslator._normalize_language_code("fil"), "tl")
        self.assertEqual(DeepLTranslator._normalize_language_code("ku"), "kmr")
        self.assertEqual(DeepLTranslator._normalize_language_code("pt"), "pt-br")
        self.assertEqual(
            DeepLTranslator._normalize_language_code("zh-TW"), "zh-hant"
        )

    def test_google_cloud_returns_translated_text(self):
        translator = GoogleCloudTranslator.__new__(GoogleCloudTranslator)
        translator._client = Mock()
        translator._supported_language_codes = {"es"}
        translator._usage_tracker = Mock()
        translator._client.translate.return_value = {"translatedText": "Hola"}

        self.assertTrue(translator.is_language_supported("ES"))
        self.assertEqual(
            translator.translate_text("Hello", "es", "en"),
            "Hola",
        )
        translator._usage_tracker.record_google_characters.assert_called_once_with(5)

    def test_google_cloud_wraps_provider_errors(self):
        translator = GoogleCloudTranslator.__new__(GoogleCloudTranslator)
        translator._client = Mock()
        translator._supported_language_codes = {"es"}
        translator._client.translate.side_effect = RuntimeError("failure")

        with self.assertRaises(TranslationError):
            translator.translate_text("Hello", "es", "en")

    def test_google_cloud_connection_test_uses_real_translation_path(self):
        translator = GoogleCloudTranslator.__new__(GoogleCloudTranslator)
        translator._client = Mock()
        translator._supported_language_codes = {"de"}
        translator._client.translate.return_value = {
            "translatedText": "Verbindungstest"
        }

        result = translator.test_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "connected")
        translator._client.translate.assert_called_once_with(
            "hi",
            format_="text",
            source_language="en",
            target_language="de",
        )

    def test_deepl_connection_test_uses_real_translation_path(self):
        translator = DeepLTranslator.__new__(DeepLTranslator)
        translator._client = Mock()
        translator._client.translate_text.return_value = Mock(
            text="Verbindungstest"
        )

        result = translator.test_connection()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "connected")
        translator._client.translate_text.assert_called_once_with(
            "hi",
            source_lang="EN",
            target_lang="de",
        )

    def test_deepl_usage_is_returned_from_the_client(self):
        translator = DeepLTranslator.__new__(DeepLTranslator)
        translator._client = Mock()
        translator._client.get_usage.return_value.character = Mock(
            valid=True,
            count=12,
            limit=500_000,
        )

        self.assertEqual(
            translator.get_usage(),
            {
                "status": "ready",
                "used": 12,
                "limit": 500_000,
                "remaining": 499_988,
                "message": "Live usage from your DeepL account.",
            },
        )

    def test_connection_test_reports_unconfigured_provider(self):
        translator = DeepLTranslator.__new__(DeepLTranslator)
        translator._client = None

        self.assertEqual(
            translator.test_connection(),
            {
                "ok": False,
                "status": "not_configured",
                "message": "Not configured",
            },
        )


if __name__ == "__main__":
    unittest.main()
