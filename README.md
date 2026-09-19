<p align="center">
  <img src="docs/images/yt-localizer-banner.svg" alt="YT Localizer by Vagabondity Walks" width="100%">
</p>

# YouTube Localizer by Vagabondity

A free-to-use, source-available, local-first YouTube metadata translator for creators. Batch-translate and publish localized YouTube video titles and descriptions in multiple languages using DeepL or Google Cloud Translation - while safely running it on your own computer. The application has no subscription fee, you only remain responsible for any usage charges imposed by the provider you choose, but there are generous free tiers in both of them, which you can use to make literally hundreds of localizations for free.
The app updates YouTube localization fields through YouTube Data API v3 and it does not replace the original title or description.

This app has no subscription fee, no app-imposed limits, publicly available source code, and it doesn't ask you to give access to your YT channel to any third-party. It's easy to install and very easy to use! Originally built and improved for localizing videos on the developer's YT city walks channel 🐸 [Vagabondity Walks](https://www.youtube.com/@vagabondity) - now sharing it so other creators can use it too. Feel free to check out the channel it was made for!

Refer to [Quick Start](#quick-start) for a guide to set this app up and start localizing your YT Channel. Refer to [Vagabondity vs ReTranslate.ai comparison](https://ytlocalizer.com/comparison/) to see the comparison between this app and ReTranslate.ai service.

> **Status:** Fully functional and actively improved.

## Preview

![Vagabondity YouTube Localizer interface](docs/images/app-overview.png)

## Requirements

- A Google account that manages a YouTube channel.
- Installed [`uv`](https://docs.astral.sh/uv/getting-started/installation/) package manager. _You do not need to install Python or anything else separately apart from `uv` for this app to work_.
- YouTube Data API v3 OAuth credentials (configured in Google Cloud).
- Access keys for at least one translation provider: DeepL API or Google Cloud Translation.

## Features

- 🚀 **Batch localization:** Translate and publish metadata for a single video, a page of videos, or the entire channel in one run.
- 🌍 **Localization-aware selection:** Review each video's source language and existing localizations before choosing target languages. Existing translations are skipped by default, with an option to replace and retranslate them.
- 🧭 **Language compatibility checks:** Before translation starts, the app verifies the video's source language and every target language against the capabilities reported by DeepL and Google Cloud Translation. Provider-only targets are clearly labelled, unsupported combinations are disabled, and videos with different source languages cannot be mixed in one batch.
- 🎬 **Flexible video library:** Filter full-length videos and Shorts, browse by page, and select individual videos, the current page, or the entire channel.
- 🔄 **Multiple translation providers:** Choose explicitly between DeepL and Google Cloud Translation for each localization run.
- 📊 **Live progress tracking:** Follow every video-and-language pair as it is processed, including published, skipped, and failed localizations with their reasons.
- 📈 **Usage and quota visibility:** View DeepL usage, locally tracked Google Cloud Translation usage, and YouTube API quota information from the **USAGE** window.
- ✅ **Provider connection checks:** Test both configured translation providers from the **TEST** window before starting a localization run. The check uses a tiny translation request and does not modify YouTube metadata.
- 🔋 **YouTube quota recovery:** When the daily YouTube API quota is exhausted, the app enters limited mode, keeps cached channel data available, shows the expected reset time, and lets you reconnect when access is restored.
- 💻 **Local-first operation:** The interface runs only on `127.0.0.1`. Credentials and provider settings are stored locally and are used only to authenticate requests to the configured services.
- 🛡️ **Original content protection:** The original video, thumbnail, title, and description remain unchanged; only additional language localizations are published.

## Quick Start

Follow the [step-by-step setup guide](https://ytlocalizer.com/setup/) to install, configure, and start YT Localizer.

## Project structure and development details

Application code lives in the `src/vagabondity_youtube_localizer` package:

- `app.py` creates the Flask application and defines its HTTP routes.
- `settings.py` reads the central local configuration.
- `localization.py` coordinates translating and publishing video metadata.
- `youtube_client.py` handles YouTube authentication, pagination, and updates.
- `translators/` contains the independent DeepL and Google Cloud providers.
- `templates/` and `static/` contain the local web interface.

### About `uv.lock`

`pyproject.toml` contains the human-readable list of the application's direct dependencies. `uv.lock` is an automatically generated dependency lock file and should not be edited manually.

The long URLs in `uv.lock` point to package files hosted by the official Python Package Index (`pypi.org` and `files.pythonhosted.org`). The file records package versions, platform-specific builds, and SHA-256 hashes so that `uv` can install reproducible dependencies and verify downloaded files. Only the build appropriate for the current operating system and processor is downloaded.

Verify the locked environment and Python syntax:

```bash
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src
```

### Security notes

- The application runs locally and listens on `127.0.0.1`, not on the public network.
- Video titles and descriptions are sent to the selected translation provider.
- YouTube OAuth credentials can update channel metadata. Review selected videos and languages before starting a batch.
- Never publish `config/settings.toml`, Google credential JSON files, or `token.pickle`.
- Revoke access at any time from your Google Account's third-party access page.

## License

Vagabondity YouTube Localizer is **source-available, free-to-use proprietary software** under the [Vagabondity Free-to-Use License](LICENSE).

You may, at no charge:

- download, install, and run the unmodified application;
- use it for personal, commercial, and monetized YouTube channels that you own or are authorized to manage;
- use it while providing localization services to clients, as long as you do not give them access to the software itself;
- inspect the public source code to verify how the application handles credentials and YouTube access;
- freely use, publish, and monetize the translations and other output produced with the application.

You may not redistribute, resell, sublicense, rebrand, or publish modified copies of the software, use its source code to create a competing product, or offer the application as a hosted service. Configuration changes and files created during normal operation are allowed.

This project is **not open source under the OSI definition**: its source is public for transparency, but reuse and redistribution are restricted. Sharing a link to the official repository is allowed and encouraged.

The project contains portions derived from [YouTube-Video-Metadata-Translator](https://github.com/jordicor/YouTube-Video-Metadata-Translator) by Jordi Cor.
Those third-party portions remain licensed separately under the MIT License and are not restricted by the Vagabondity Free-to-Use License.

See [`LICENSE`](LICENSE), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and [`LICENSES/MIT-JORDI-COR.txt`](LICENSES/MIT-JORDI-COR.txt) for the complete terms.

## Problems or bugs?

If you run into a problem, find a bug, or need help with the app, please
[create a GitHub Issue](https://github.com/Polovinkin/Vagabondity-YouTube-Localizer/issues/new)
and describe what happened. If possible, include the full error message shown in Terminal and all the steps that led to the problem. More details - the better!

## Support YT Localizer

If YT Localizer helped you, you can support the project with whatever amount you feel it was worth to you.

<a href="https://www.buymeacoffee.com/polovinkin">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Support YT Localizer on Buy Me a Coffee" height="50">
</a>
