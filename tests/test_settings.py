import tempfile
import unittest
from pathlib import Path

from vagabondity_youtube_localizer.settings import load_settings


class SettingsTests(unittest.TestCase):
    def test_toml_contains_all_provider_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.toml"
            settings_path.write_text(
                """
[translation]
default_provider = "deepl"
[youtube]
oauth_client_file = "config/youtube.json"
token_file = "config/token.pickle"
[google]
credentials_file = "config/google.json"
[deepl]
api_key = "test-key"
""".strip(),
                encoding="utf-8",
            )

            settings = load_settings(settings_path)

        self.assertEqual(settings.default_translation_provider, "deepl")
        self.assertEqual(settings.deepl_api_key, "test-key")
        self.assertEqual(
            settings.google_credentials_file,
            "config/google.json",
        )

if __name__ == "__main__":
    unittest.main()
