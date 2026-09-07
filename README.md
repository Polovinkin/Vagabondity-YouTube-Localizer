# Vagabondity YouTube Localizer

A local app for translating YouTube video titles and descriptions into multiple
languages and publishing those translations directly to your channel.

Review existing localizations, and then choose videos and target languages in the app,
and publish translations directly to YouTube — without changing the
original title or description.

Created by the authors of [Vagabondity Walks](https://www.youtube.com/@vagabondity) YouTube city walks channel.

> **Status:** Actively developed. Expect occasional changes and rough edges.

## Preview

![Vagabondity YouTube Localizer interface](docs/images/app-overview.png)

## Quick Start

**First-time setup typically takes about 10 minutes.**
Most of that time is spent in Google Cloud creating access for your YouTube channel.
After setup, starting the app normally takes one command and about a minute.

You need:

- a Google account that manages your YouTube channel
- this project downloaded to your computer
- one translation provider. **DeepL is the simplest option to start with.**

You do **not** need to install Python, which this app is running on. The `uv` tool downloads the correct Python
version and all required packages automatically.

### 1. Download the app and open its folder in Terminal

On this [GitHub page](https://github.com/Polovinkin/Vagabondity-YouTube-Localizer),
click green button **Code → Download ZIP**, extract the ZIP, and open the extracted `Vagabondity-YouTube-Localizer` folder.

Then open Terminal in that folder:

- **macOS:** open the **Terminal** app, type `cd ` (including the space), drag
  the `Vagabondity-YouTube-Localizer` folder from Finder into the Terminal
  window, and press Enter.
- **Windows:** open the folder in File Explorer, click the address bar, type
  `powershell`, and press Enter.

If you already downloaded the project and opened Terminal in its folder, continue to the next step.

### 2. Install uv

Copy the command for your operating system into Terminal and press Enter.

macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen Terminal after installation. Alternative installation methods
are available in the official [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### 3. Create your private settings file

Copy the next command into Terminal and press Enter. It will use the template file to create a config file you will use.
You only need to create this file once.

macOS and Linux:

```bash
cp config/settings.example.toml config/settings.toml
```

Windows PowerShell:

```powershell
Copy-Item config/settings.example.toml config/settings.toml
```

### 4. Give the app access to your YouTube channel

This is required for the app to use data from your YouTube channel. You have to manually create your own Google Cloud project and configure it for that.

1. Open [Google Cloud Console](https://console.cloud.google.com) and create a project, you can use any name, but you can name this project like "YT Localizer". Or you can just select an existing project. Pick this project as an active one.
2. [Enable YouTube Data API v3](https://console.cloud.google.com/marketplace/product/google/youtube.googleapis.com)
   for that project. You can use your emails in the fields (it's your own project after all).
3. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview).
   If asked, click **Get started**, complete the basic app information, and choose **External** as the audience.
4. Open **Audience → Test users**, add the email of the Google account that manages your YouTube channel, and save it.
5. Open [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients), click **Create client**, and select **Desktop app**. You can leave the default name.
6. When you press **Create**, the window will appear, when you have to download the client JSON file (button below), rename it to `account_client_secrets_main.json`, and move it into the project's `config` folder, so the final path must be `config/account_client_secrets_main.json`.

### 5. Add a translation provider

The easiest starting option is DeepL:

1. Choose an available API plan on the [DeepL API plans page](https://www.deepl.com/pro-api) - the Developer plan is the one you need, with the free 1 million symbols quota.
2. Copy your API Key from the [DeepL API Keys & Limits](https://www.deepl.com/en/your-account/keys) section of your DeepL account.
3. Open `config/settings.toml` in any text editor and replace the placeholder:

```toml
[deepl]
api_key = "paste_your_deepl_api_key_here"
```

DeepL's available plans and usage allowances can change, so check the current terms on its plans page.
If you prefer Google Cloud Translation, follow the [Google Cloud Translation setup](#google-cloud-translation-optional) below.

### 6. Start the app

Run this command from the project folder:

```bash
uv run vagabondity-youtube-localizer
```

The first run takes longer because `uv` downloads Python and the app's packages.
It also opens a Google authorization page in your browser. Sign in with the
user you added in step 4 and approve the requested YouTube permissions.

Keep Terminal open while using the app, then open:

<http://127.0.0.1:5050>

### 7. Test with one video first

1. Click **TEST** button in the app and test that translation-provider connection works.
2. Check that your configured provider is chosen on the main screen selector (DeepL or Google).
2. Select one public or unlisted video and pick one language that is not already published.
4. Start localization and follow the progress window.
5. Confirm the result in YouTube Studio before localizing more videos.

To stop the app, return to Terminal and press `Ctrl+C`.

## Features

- 🚀 **Batch localization:** Translate and publish metadata for a single video, a page of videos, or the entire channel in one run.
- 🌍 **Localization-aware selection:** Review each video's source language and existing localizations before choosing target languages. Existing translations are skipped by default, with an option to replace and retranslate them.
- 🎬 **Flexible video library:** Filter full-length videos and Shorts, browse by page, and select individual videos, the current page, or the entire channel.
- 🔄 **Multiple translation providers:** Choose explicitly between DeepL and Google Cloud Translation for each localization run.
- 📊 **Live progress tracking:** Follow every video-and-language pair as it is processed, including published, skipped, and failed localizations with their reasons.
- 📈 **Usage and quota visibility:** View DeepL usage, locally tracked Google Cloud Translation usage, and YouTube API quota information from the **USAGE** window.
- ✅ **Provider connection checks:** Test both configured translation providers from the **TEST** window before starting a localization run. The check uses a tiny translation request and does not modify YouTube metadata.
- 🔋 **YouTube quota recovery:** When the daily YouTube API quota is exhausted, the app enters limited mode, keeps cached channel data available, shows the expected reset time, and lets you reconnect when access is restored.
- 💻 **Local-first operation:** The interface runs only on `127.0.0.1`. Credentials and provider settings are stored locally and are used only to authenticate requests to the configured services.
- 🛡️ **Original content protection:** The original video, thumbnail, title, and description remain unchanged; only additional language localizations are published.

## Requirements

- A Google account that manages a YouTube channel.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) package manager.
- YouTube Data API v3 OAuth credentials (configured in Google Cloud).
- At least one translation provider: DeepL API or Google Cloud Translation.

You do not need to install Python separately. See [Quick Start](#quick-start) for
the complete first-time setup in the correct order.

## Local configuration in config/settings.toml

`config/settings.toml` is the central configuration file for both translation providers and YouTube access.
Your private settings and credential files are excluded from Git by `.gitignore`.
Create your private settings file by renaming `config/settings.example.toml` to `config/settings.toml` or by running this command in Terminal in the repository root:

```bash
cp config/settings.example.toml config/settings.toml
```

The two Google credentials are in JSON files because they are downloaded from Google in that format. 
The settings file keeps their paths and the DeepL key in one place.

## Detailed setup reference

The Quick Start above is enough for most people. This section explains the same
credentials in more detail and includes the optional Google translation provider.

### Google setup

#### YouTube access (required)

1. Create or select a project in the
   [Google Cloud Console](https://console.cloud.google.com).
2. Enable **YouTube Data API v3** ([link](https://console.cloud.google.com/marketplace/product/google/youtube.googleapis.com)).
##### Configure Google Auth Platform

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

##### Create the OAuth client

1. Open **Google Auth Platform → Clients** ([link](https://console.cloud.google.com/auth/clients)).
2. Create an OAuth 2.0 Client ID of type **Desktop app**.
3. Download the resulting client JSON, rename it, and save it to the repository as:

```text
config/account_client_secrets_main.json
```

The first run opens a Google authorization page. The resulting local OAuth
token is saved as `token.pickle` and is excluded from Git.

### Translation provider setup (choose at least one)

#### DeepL

**Recommended for the simplest setup.** Create a DeepL API account using one of
the currently available plans. Plan names, availability, limits, and billing
requirements can change; check the [DeepL API plans page](https://www.deepl.com/pro-api)
for the current terms.

Open `config/settings.toml` and paste the key from **DeepL → Account → API Keys & Limits**:

```toml
[deepl]
api_key = "paste_your_deepl_api_key_here"
```

#### Google Cloud Translation (optional)

This is required only if you want to use Google Cloud Translation.

1. Enable **Cloud Translation API** and billing in the same Google Cloud project.
2. Create a service account with the **Cloud Translation API User** role.
3. Inside this service account, click on Keys tab and create a JSON key for that service account by pressing "Add key -> Create new key", save it, rename and put to config folder as:

```text
config/translate_key.json
```

Do not commit or share `config/settings.toml`, credential JSON files, or
`token.pickle`. These files are excluded from Git. The app keeps them on your
computer and uses them only when authenticating with the configured Google,
YouTube, and translation services.

## Running the app after setup

Running the app is designed to be extremely simple! You just need to run this command from the repository directory, and that's it:

```bash
uv run vagabondity-youtube-localizer
```

On the first run this `uv` command creates `.venv`, installs the exact locked dependencies and required packages,
and downloads Python 3.12 if needed. The app itself does not open a browser tab automatically; open <http://127.0.0.1:5050> after authorization.

### First Google authorization

On first launch, Google may show an “Google hasn’t verified this app” warning because the OAuth app is in Testing mode.

This is expected. If this is your Google Cloud project and the app name is correct:
1. Sign in with an account added to Google Auth Platform → Audience → Test users.
2. Click Continue and approve the requested YouTube permissions. If you see `Error 403: access_denied`, add the selected Google account to the project’s Test users.
3. After authorization, window closes, return to the application by opening <http://127.0.0.1:5050>.

The token is saved locally in `token.pickle`.

While the Google OAuth app remains in **Testing** mode, Google normally expires
the authorization after seven days. If the app asks you to sign in again later,
repeat the same authorization with your listed test-user account.

Stop the application with Ctrl+C at any time.

### Test translation provider connections

The app lets you verify that Google Cloud Translation and DeepL keys work fine before localizing any videos.
In order to do so, click **Test** in **Translation provider** window. The check does not read or update YouTube metadata, it only verifies the actual credentials, API access, and translation request (not just whether a key file) exists - by asking each provider to translate the short phrase `hi` into German (uses only a few characters of translation quota).

## Your first localization

1. Start by selecting one public or unlisted video.
2. Select either **DeepL** or **Google** in the translation-provider switch (depends on which configs did you add).
3. Choose one language that has not been localized yet (all localized version will be shown in the UI).
4. Run the translation and follow the progress of the translation in the window.
5. After it's done - confirm the localized title and description in YouTube Studio.
6. Test **retranslate existing languages** on that same localization only if you intentionally want to replace it.
7. If everything works fine - feel free to translate more videos!

## Common setup problems

- **`uv: command not found`:** close and reopen Terminal after installing `uv`.
  If it still fails, use another method from the
  [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).
- **The app cannot find `config/settings.toml`:** make sure you opened Terminal
  in the project folder and completed step 3 of Quick Start.
- **The app cannot find the OAuth JSON file:** confirm that the downloaded file
  is named exactly `account_client_secrets_main.json` and is inside `config`.
- **`Error 403: access_denied`:** add the Google account you selected to
  **Google Auth Platform → Audience → Test users**, then try again.
- **Google asks you to authorize again after seven days:** this is normal while
  the OAuth app remains in Testing mode.
- **The local page does not open:** keep Terminal running, check it for an error,
  and open <http://127.0.0.1:5050> manually.

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
