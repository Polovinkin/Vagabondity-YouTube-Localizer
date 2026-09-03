# Vagabondity YouTube Localizer


Bulk-translate YouTube video titles and descriptions, review existing
localizations, and publish the results back to YouTube. All is done safely and predictably.

Built by the author of [Vagabondity Walks](https://www.youtube.com/@vagabondity) channel
for creators who want to localize YouTube metadata at scale.

Product is in active development! :)

## Features

- Translate multiple videos and languages in one run.
- Switch explicitly between DeepL and Google Cloud Translation and test both provider connections before starting a localization run.
- Retranslate and overwrite existing localizations explicitly.
- Keep the original video, thumbnail, title, and description unchanged.
- Keep local provider settings together in the `config/` directory.
- Store API credentials locally; the app binds only to `127.0.0.1`.

## Requirements

- A Google account that manages a YouTube channel.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- YouTube Data API v3 OAuth credentials.
- At least one translation provider: DeepL API or Google Cloud Translation.

Python or anything else does not need to be installed separately. Python package and project manager `uv` downloads and manages the needed Python version automatically!

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

`config/settings.toml` is the central configuration file for both translation
providers and YouTube access. Create your private settings file by renaming `config/settings.example.toml` to `config/settings.toml` or by running this command in Terminal:

```bash
cp config/settings.example.toml config/settings.toml
```

The two Google credentials are in JSON files because they are downloaded from
Google in that format. The settings file keeps their paths and the DeepL key in
one place. `config/settings.toml` and credential JSON files are excluded from
Git by `.gitignore` file, they are not shared and completely private.

## Google setup

### 1. YouTube access (required)

1. Create or select a project in the
   [Google Cloud Console](https://console.cloud.google.com/).
2. Enable **YouTube Data API v3**. You can search for it in search bar and click "Enable" there.

#### 1.1 Configure Google Auth Platform

1. Open **Google Auth Platform** for the same Google Cloud project (also find it in search).
2. If Google Auth Platform has not been initialized for this project yet, click
   **Get started** and fill in the required app name, support email, and
   developer contact fields. You do not need to add a logo, homepage, or privacy
   policy for personal testing and usage.
3. Under **Test users**, click **Add users**, add the Google account that manages
   your YouTube channel, and save the changes.

Only accounts listed under **Test users** can authorize the application while
its publishing status is **Testing**. If you don't add your Google account here, you will not be
able to log-in to your Google account when app starts.

#### 1.2 Create the OAuth client

1. Open **Google Auth Platform → Clients**.
2. Create an OAuth 2.0 Client ID of type **Desktop app**.
3. Download the resulting client JSON, rename it, and save it to the repository as:

```text
config/account_client_secrets_main.json
```

The first run opens a Google authorization page. The resulting local OAuth
token is saved as `token.pickle` and is excluded from Git.

### 2. Google Cloud Translation (optional, if you choose DeepL)

This is required only if you want to use Google Cloud Translation.

1. Enable **Cloud Translation API** and billing in the same Google Cloud
   project.
2. Create a service account with the **Cloud Translation API User** role.
3. Inside this service account, click on Keys tab and create a JSON key for that service account by pressing "Add key -> Create new key", save it, rename and put to config folder as:

```text
config/translate_key.json
```

## DeepL setup (optional, if you choose Google Translate)

In order to use DeepL, you need to register in DeepL API, Free tier is, well, free :), you don't need to add any billing info.
Open `config/settings.toml` and paste the key from
**DeepL → Account → API Keys & Limits**:

```toml
[deepl]
api_key = "your-deepl-api-key"
```

Do not commit or share `config/settings.toml`, credential JSON files, or
`token.pickle`. All credential JSON files and API keys are excluded from Git by `.gitignore` file, they are completely private and don't leave your device - apart from using them to access translation services.

## Run

Running the app is extremely simple! You just need to run this command from the repository directory, and that's it:

```bash
uv run vagabondity-youtube-localizer
```

On the first run, `uv` creates `.venv`, installs the exact locked dependencies,
and downloads Python 3.12 if needed. Open <http://127.0.0.1:5050> if the browser
does not open automatically.

### First Google authorization

On first launch, Google may show an “Google hasn’t verified this app” warning because the OAuth app is in Testing mode.

It's expected and it's find. If this is your Google Cloud project and the app name is correct:
1. Sign in with an account added to Google Auth Platform → Audience → Test users.
2. Click Continue and approve the requested YouTube permissions. If you see `Error 403: access_denied`, add the selected Google account to the project’s Test users.
3. After authorization, window closes, return to the application by opening <http://127.0.0.1:5050>.

The token is saved locally in `token.pickle`.

Stop the application with Ctrl+C at any time.

### Test translation-provider connections

Service has a feature which allows to verify that Google Cloud Translation and DeepL keys work fine before localizing any videos.
In order to do so, click **Test** in **Translation provider** window. The check sends the short
phrase `Connection test` through each configured provider, so it verifies the
actual credentials, API access, and translation request — not just whether a key file exists.

The check does not read or update YouTube metadata. It uses only a few
characters of translation quota for each configured provider.

## Safe first test

1. Start with selecting one public or unlisted video.
2. Select either **DeepL** or **Google** in the translation-provider switch.
3. Choose one language that has not been localized yet.
4. Run the translation and look for `DeepL completed` in the terminal (if you used DeepL)
5. Confirm the localized title and description in YouTube Studio.
6. Test **retranslate existing languages** on that same localization only if
   you intentionally want to replace it.
7. If everything works fine - feel free to bulk translate another videos! :)

## Project structure

Application code lives in the `src/vagabondity_youtube_localizer` package:

- `app.py` creates the Flask application and defines its HTTP routes.
- `settings.py` reads the central local configuration.
- `localization.py` coordinates translating and publishing video metadata.
- `youtube_client.py` handles YouTube authentication, pagination, and updates.
- `translators/` contains the independent DeepL and Google Cloud providers.
- `templates/` and `static/` contain the local web interface.

## Development checks

Verify the locked environment and Python syntax:

```bash
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src
```

## Security notes

- The application runs locally and listens on `127.0.0.1`, not on the public
  network.
- Video titles and descriptions are sent to the selected translation provider.
- YouTube OAuth credentials can update channel metadata. Review selected videos
  and languages before starting a batch.
- Never publish `config/settings.toml`, Google credential JSON files, or
  `token.pickle`.
- Revoke access at any time from your Google Account's third-party access page.

### About `uv.lock`

`pyproject.toml` contains the human-readable list of the application's direct dependencies. `uv.lock` is an automatically generated dependency lock file and should not be edited manually.

The long URLs in `uv.lock` point to package files hosted by the official Python Package Index (`pypi.org` and `files.pythonhosted.org`). The file records package versions, platform-specific builds, and SHA-256 hashes so that `uv` can install reproducible dependencies and verify downloaded files. Only the build appropriate for the current operating system and processor is downloaded.

## License

This is proprietary software. All rights are reserved.

The project contains portions derived from
[YouTube-Video-Metadata-Translator](https://github.com/jordicor/YouTube-Video-Metadata-Translator)
by Jordi Cor. Those portions remain available under the MIT License.

See `LICENSE` and `THIRD_PARTY_NOTICES.md`.