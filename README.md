# Vagabondity YouTube Localizer

A local web app which you can use to translate YouTube video metadata (titles and descriptions)
into multiple languages by your choice - free of charge! All you need is `uv` package and project manager which is installed by a single command,
and you need to create dev profile in a translator provider of choice (DeepL or Google) - I explain how down below.

Review existing localizations, and then choose videos and target languages in the app,
and publish translations directly to YouTube — without changing the
original title or description.

Created by the authors of [Vagabondity Walks](https://www.youtube.com/@vagabondity) YouTube city walks channel.

> **Status:** Actively developed. Expect occasional changes and rough edges.

## Preview

![Vagabondity YouTube Localizer interface](docs/images/app-overview.png)

## Features

- **Batch localization:** Translate and publish metadata for a single video, a page of videos, or the entire channel in one run.
- **Localization-aware selection:** Review each video's source language and existing localizations before choosing target languages. Existing translations are skipped by default, with an option to replace and retranslate them.
- **Flexible video library:** Filter full-length videos and Shorts, browse by page, and select individual videos, the current page, or the entire channel.
- **Multiple translation providers:** Choose explicitly between DeepL and Google Cloud Translation for each localization run.
- **Live progress tracking:** Follow every video-and-language pair as it is processed, including published, skipped, and failed localizations with their reasons.
- **Usage and quota visibility:** View DeepL usage, locally tracked Google Cloud Translation usage, and YouTube API quota information from the **USAGE** window.
- **Provider connection checks:** Test both configured translation providers from the **TEST** window before starting a localization run. The check uses a tiny translation request and does not modify YouTube metadata.
- **YouTube quota recovery:** When the daily YouTube API quota is exhausted, the app enters limited mode, keeps cached channel data available, shows the expected reset time, and lets you reconnect when access is restored.
- **Local-first operation:** The interface runs only on `127.0.0.1`, while credentials and provider settings remain safely in the local `config/` directory and don't leave your device.
- **Original content protection:** The original video, thumbnail, title, and description remain unchanged; only additional language localizations are published.

## Requirements

- A Google account that manages a YouTube channel.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) package manager.
- YouTube Data API v3 OAuth credentials (configured in Google Cloud).
- At least one translation provider: DeepL API or Google Cloud Translation.

You do not need to install Python separately - Python package and project manager `uv` downloads and manages the needed Python version automatically!

### Install uv

macOS with Homebrew:

```bash
brew install uv
```

Windows with WinGet:

```powershell
winget install --id=astral-sh.uv -e
```

For Linux and other installation methods, see the
[`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

## Local configuration in config/settings.toml

`config/settings.toml` is the central configuration file for both translation providers and YouTube access.
They are excluded from Git by `.gitignore` file, they are not shared and completely private.
Create your private settings file by renaming `config/settings.example.toml` to `config/settings.toml` or by running this command in Terminal in the repository root:

```bash
cp config/settings.example.toml config/settings.toml
```

The two Google credentials are in JSON files because they are downloaded from Google in that format. 
The settings file keeps their paths and the DeepL key in one place.

## Google setup

### 1. YouTube access (required)

1. Create or select a project in the
   [Google Cloud Console](https://console.cloud.google.com).
2. Enable **YouTube Data API v3** ([link](https://console.cloud.google.com/marketplace/product/google/youtube.googleapis.com)).
#### 1.1 Configure Google Auth Platform

1. Open **Google Auth Platform** ([link](https://console.cloud.google.com/auth/overview)) for the same Google Cloud project.
2. If Google Auth Platform has not been initialized for this project yet, click
   **Get started** and fill in the required app name, support email, and
   developer contact fields. You do not need to add a logo, homepage, or privacy
   policy for personal testing and usage.
3. Under **Test users**, click **Add users**, add the Google account that manages
   your YouTube channel, and save the changes.

Only accounts listed under **Test users** can authorize the application while
its publishing status is **Testing**. If you don't add your Google account here, you will not be
able to log in to your Google account when app starts.

#### 1.2 Create the OAuth client

1. Open **Google Auth Platform → Clients** ([link](https://console.cloud.google.com/auth/clients)).
2. Create an OAuth 2.0 Client ID of type **Desktop app**.
3. Download the resulting client JSON, rename it, and save it to the repository as:

```text
config/account_client_secrets_main.json
```

The first run opens a Google authorization page. The resulting local OAuth
token is saved as `token.pickle` and is excluded from Git.

## Translation provider setup (required, pick one!)

### DeepL

_Recommended_ - it's usually higher quality than Google and you don't need to create a billing account or connect your bank card (which you need to do in order to use Google Cloud Translation).

In order to use DeepL, you need to start a Developer plan in [DeepL API](https://www.deepl.com/en/pro#api). Developer is a free tier there which includes the one-time credit of 1 million characters (it's enough to make literally hundreds of localization to various languages). You don't need to add any billing info for that, you just have to register there for that, it's not hard to do.
Open `config/settings.toml` and paste the key from **DeepL → Account → API Keys & Limits**:

```toml
[deepl]
api_key = "paste_your_deepl_api_key_here"
```

### Google Cloud Translation

This is required only if you want to use Google Cloud Translation.

1. Enable **Cloud Translation API** and billing in the same Google Cloud project.
2. Create a service account with the **Cloud Translation API User** role.
3. Inside this service account, click on Keys tab and create a JSON key for that service account by pressing "Add key -> Create new key", save it, rename and put to config folder as:

```text
config/translate_key.json
```

Do not commit or share `config/settings.toml`, credential JSON files, or
`token.pickle`. All credential JSON files and API keys are excluded from Git by `.gitignore` file, they are completely private and don't leave your device - apart from using them to access translation services.

## Run

Running the app is designed to be extremely simple! You just need to run this command from the repository directory, and that's it:

```bash
uv run vagabondity-youtube-localizer
```

On the first run this `uv` command creates `.venv`, installs the exact locked dependencies and required packages
and downloads Python 3.12 if needed. Open <http://127.0.0.1:5050> if the browser does not open automatically.

### First Google authorization

On first launch, Google may show an “Google hasn’t verified this app” warning because the OAuth app is in Testing mode.

This is expected. If this is your Google Cloud project and the app name is correct:
1. Sign in with an account added to Google Auth Platform → Audience → Test users.
2. Click Continue and approve the requested YouTube permissions. If you see `Error 403: access_denied`, add the selected Google account to the project’s Test users.
3. After authorization, window closes, return to the application by opening <http://127.0.0.1:5050>.

The token is saved locally in `token.pickle`.

Stop the application with Ctrl+C at any time.

### Test translation provider connections

The app lets you verify that Google Cloud Translation and DeepL keys work fine before localizing any videos.
In order to do so, click **Test** in **Translation provider** window. The check does not read or update YouTube metadata, it only verifies the actual credentials, API access, and translation request (not just whether a key file) exists - by asking each provider to translate the short phrase `hi` into German (uses only a few characters of translation quota).

## Give it a try! How to test the app

1. Start by selecting one public or unlisted video.
2. Select either **DeepL** or **Google** in the translation-provider switch (depends on which configs did you add).
3. Choose one language that has not been localized yet (all localized version will be shown in the UI).
4. Run the translation and follow the progress of the translation in the window.
5. After it's done - confirm the localized title and description in YouTube Studio.
6. Test **retranslate existing languages** on that same localization only if you intentionally want to replace it.
7. If everything works fine - feel free to translate more videos!

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

This is proprietary software. All rights are reserved.

The project contains portions derived from [YouTube-Video-Metadata-Translator](https://github.com/jordicor/YouTube-Video-Metadata-Translator) by Jordi Cor.
Those portions are licensed under the MIT License.

See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
