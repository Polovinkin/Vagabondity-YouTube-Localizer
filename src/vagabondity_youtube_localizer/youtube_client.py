import html
import os
import pickle
import re

import googleapiclient.errors
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# YouTube API configuration
scopes = ["https://www.googleapis.com/auth/youtube"]
api_service_name = "youtube"
api_version = "v3"
SHORTS_MAX_DURATION_SECONDS = 180
VIDEO_FILTERS = {"all", "videos", "shorts"}
THUMBNAIL_QUALITY_ORDER = ("maxres", "standard", "high", "medium", "default")
YOUTUBE_DEFAULT_DAILY_QUOTA = 10_000
YOUTUBE_LOCALIZATION_BATCH_QUOTA_COST = 51

LANGUAGE_FLAGS = {
    "Afrikaans": "🇿🇦",
    "Albanian": "🇦🇱🇽🇰",
    "Amharic": "🇪🇹",
    "Arabic": "🇸🇦🇪🇬🇦🇪",
    "Armenian": "🇦🇲",
    "Azerbaijani": "🇦🇿",
    "Bangla": "🇧🇩🇮🇳",
    "Basque": "🇪🇸🇫🇷",
    "Belarusian": "🇧🇾",
    "Bosnian": "🇧🇦",
    "Bulgarian": "🇧🇬",
    "Burmese": "🇲🇲",
    "Catalan": "🇪🇸🇦🇩",
    "Chinese (China)": "🇨🇳",
    "Chinese (Taiwan)": "🇹🇼",
    "Croatian": "🇭🇷",
    "Czech": "🇨🇿",
    "Danish": "🇩🇰",
    "Dutch": "🇳🇱🇧🇪",
    "English": "🇺🇸🇬🇧🇨🇦",
    "Estonian": "🇪🇪",
    "Finnish": "🇫🇮",
    "French": "🇫🇷🇨🇦🇧🇪",
    "Galician": "🇪🇸",
    "Georgian": "🇬🇪",
    "German": "🇩🇪🇦🇹🇨🇭",
    "Gujarati": "🇮🇳",
    "Hebrew": "🇮🇱",
    "Hindi": "🇮🇳",
    "Hungarian": "🇭🇺",
    "Icelandic": "🇮🇸",
    "Indonesian": "🇮🇩",
    "Italian": "🇮🇹🇨🇭",
    "Japanese": "🇯🇵",
    "Kannada": "🇮🇳",
    "Kazakh": "🇰🇿",
    "Khmer": "🇰🇭",
    "Korean": "🇰🇷",
    "Kyrgyz": "🇰🇬",
    "Lao": "🇱🇦",
    "Latvian": "🇱🇻",
    "Lithuanian": "🇱🇹",
    "Macedonian": "🇲🇰",
    "Malay": "🇲🇾🇸🇬🇧🇳",
    "Malayalam": "🇮🇳",
    "Marathi": "🇮🇳",
    "Mongolian": "🇲🇳",
    "Nepali": "🇳🇵",
    "Norwegian": "🇳🇴",
    "Odia": "🇮🇳",
    "Persian": "🇮🇷🇦🇫",
    "Polish": "🇵🇱",
    "Portuguese": "🇧🇷🇵🇹",
    "Punjabi": "🇵🇰🇮🇳",
    "Romanian": "🇷🇴🇲🇩",
    "Russian": "🇷🇺",
    "Serbian": "🇷🇸",
    "Sinhala": "🇱🇰",
    "Slovak": "🇸🇰",
    "Slovenian": "🇸🇮",
    "Spanish": "🇪🇸🇲🇽🇦🇷",
    "Swahili": "🇹🇿🇰🇪",
    "Swedish": "🇸🇪🇫🇮",
    "Tamil": "🇮🇳🇱🇰🇸🇬",
    "Telugu": "🇮🇳",
    "Thai": "🇹🇭",
    "Turkish": "🇹🇷",
    "Ukrainian": "🇺🇦",
    "Urdu": "🇵🇰🇮🇳",
    "Vietnamese": "🇻🇳",
}


def parse_iso8601_duration(value):
    """Convert a YouTube ISO 8601 duration to seconds."""
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T"
        r"(?:(?P<hours>\d+)H)?"
        r"(?:(?P<minutes>\d+)M)?"
        r"(?:(?P<seconds>\d+)S)?",
        value or "",
    )
    if not match:
        return None

    parts = {name: int(number or 0) for name, number in match.groupdict().items()}
    return (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )


def best_thumbnail_url(thumbnails):
    """Return the highest-resolution thumbnail URL exposed by YouTube."""
    for quality in THUMBNAIL_QUALITY_ORDER:
        url = thumbnails.get(quality, {}).get("url")
        if url:
            return url
    return ""


def normalize_language_code(language_code):
    """Collapse YouTube locale variants to the language choices used by the app."""
    if not language_code:
        return None

    normalized = str(language_code).strip().replace("_", "-").lower()
    aliases = {
        "he": "iw",
        "zh-cn": "zh-CN",
        "zh-hans": "zh-CN",
        "zh-tw": "zh-TW",
        "zh-hant": "zh-TW",
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized.split("-", 1)[0]


class YouTubeClient:
    def __init__(
        self,
        oauth_client_file="config/account_client_secrets_main.json",
        token_file="token.pickle",
    ):
        self.credentials = None
        self.oauth_client_file = oauth_client_file
        self.token_file = token_file
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        self.page_videos = []
        self.all_videos_cache = [] # Cache for when option "ALL" is selected
        self.video_inventory = []
        self.video_filter = "all"
        self.youtube = None
        self.channel_thumbnail = ''
        self.channel_name = ''
        self.uploads_id = ''
        self.next_page_token = None
        self.page_tokens = {}  # Store page tokens for efficient pagination
        self.results_per_page = 10
        self.per_page_option_index = 0
        self.current_page = 1
        self.videos_trimmed = 0
        self.videos_skipped = 0
        self.error_code = ''
        self.total_video_count = 0
        self.allowed_languages = []
        
        self.code_to_name = {
            "af": "Afrikaans",
            "am": "Amharic",
            "ar": "Arabic",
            "az": "Azerbaijani",
            "be": "Belarusian",
            "bg": "Bulgarian",
            "bn": "Bangla",
            "bs": "Bosnian",
            "ca": "Catalan",
            "cs": "Czech",
            "da": "Danish",
            "de": "German",
            "en": "English",
            "es": "Spanish",
            "et": "Estonian",
            "eu": "Basque",
            "fa": "Persian",
            "fi": "Finnish",
            "fr": "French",
            "gl": "Galician",
            "gu": "Gujarati",
            "hi": "Hindi",
            "hr": "Croatian",
            "hu": "Hungarian",
            "hy": "Armenian",
            "id": "Indonesian",
            "is": "Icelandic",
            "it": "Italian",
            "iw": "Hebrew",
            "ja": "Japanese",
            "ka": "Georgian",
            "kk": "Kazakh",
            "km": "Khmer",
            "kn": "Kannada",
            "ko": "Korean",
            "ky": "Kyrgyz",
            "lo": "Lao",
            "lt": "Lithuanian",
            "lv": "Latvian",
            "mk": "Macedonian",
            "ml": "Malayalam",
            "mn": "Mongolian",
            "mr": "Marathi",
            "ms": "Malay",
            "my": "Burmese",
            "no": "Norwegian",
            "ne": "Nepali",
            "nl": "Dutch",
            "or": "Odia",
            "pa": "Punjabi",
            "pl": "Polish",
            "pt": "Portuguese",
            "ro": "Romanian",
            "ru": "Russian",
            "si": "Sinhala",
            "sk": "Slovak",
            "sl": "Slovenian",
            "sq": "Albanian",
            "sr": "Serbian",
            "sv": "Swedish",
            "sw": "Swahili",
            "ta": "Tamil",
            "te": "Telugu",
            "th": "Thai",
            "tr": "Turkish",
            "uk": "Ukrainian",
            "ur": "Urdu",
            "vi": "Vietnamese",
            "zh-CN": "Chinese (China)",
            "zh-TW": "Chinese (Taiwan)",
        }
        self.name_to_code = {val: key for (key, val) in self.code_to_name.items()}
        priority_language_names = [
            "English",
            "Russian",
            "Spanish",
            "Portuguese",
            "Japanese",
            "German",
            "French",
            "Korean",
            "Italian",
            "Polish",
            "Turkish",
            "Indonesian",
            "Arabic",
            "Hindi",
            "Vietnamese",
            "Thai",
            "Chinese (Taiwan)",
            "Chinese (China)",
        ]
        remaining_language_names = sorted(
            set(self.name_to_code) - set(priority_language_names)
        )
        self.language_names_in_display_order = (
            priority_language_names + remaining_language_names
        )

        self.check_credentials()
        self.youtube = build(
            api_service_name, api_version, credentials=self.credentials)
        self.set_uploads_id()
        if self.error_code == '':
            self.get_total_video_count()
            # We don't need to load the page here, home() will do it.
            # self.set_video_page(1)

    @property
    def num_pages(self):
        if self.results_per_page == -1:  # "ALL" option
            return 1
        return max(
            1,
            (self.filtered_video_count + self.results_per_page - 1)
            // self.results_per_page,
        )

    @property
    def filtered_videos(self):
        if self.video_filter == "shorts":
            return [video for video in self.video_inventory if video.is_short]
        if self.video_filter == "videos":
            return [video for video in self.video_inventory if not video.is_short]
        return list(self.video_inventory)

    @property
    def filtered_video_count(self):
        if not self.video_inventory and self.video_filter == "all":
            return self.total_video_count
        return len(self.filtered_videos)

    @property
    def video_filter_counts(self):
        shorts = sum(video.is_short for video in self.video_inventory)
        return {
            "all": len(self.video_inventory),
            "videos": len(self.video_inventory) - shorts,
            "shorts": shorts,
        }

    def check_credentials(self):
        """Check and refresh OAuth credentials"""
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as token:
                self.credentials = pickle.load(token)
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                except RefreshError:
                    self.credentials = None
            if not self.credentials:
                # Get credentials and create an API client
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_file=self.oauth_client_file, scopes=scopes)
                flow.run_local_server(port=8080, prompt='consent', authorization_prompt_message='')
                self.credentials = flow.credentials
                with open(self.token_file, "wb") as token_file:
                    pickle.dump(self.credentials, token_file)

    def clear_video_cache(self):
        """Clears all in-memory video data to force a re-fetch on the next page load."""
        self.page_videos = []
        self.all_videos_cache = []
        self.video_inventory = []
        self.page_tokens = {} # Important to reset this as well
        print("In-memory video cache cleared.")

    def refresh_video_cache(self):
        """Refresh video data without losing the last usable cache on failure."""
        previous_error_code = self.error_code
        cached_state = {
            "page_videos": self.page_videos,
            "all_videos_cache": self.all_videos_cache,
            "video_inventory": self.video_inventory,
            "page_tokens": self.page_tokens,
            "total_video_count": self.total_video_count,
        }
        self.page_videos = []
        self.all_videos_cache = []
        self.video_inventory = []
        self.page_tokens = {}
        self.error_code = ""
        transport_failed = False
        try:
            if not self.uploads_id:
                self.set_uploads_id()
                if not self.error_code:
                    self.get_total_video_count()
            if not self.error_code:
                self.load_video_inventory()
        except OSError as exc:
            print(f"Could not refresh YouTube video cache: {exc}")
            self.error_code = previous_error_code
            transport_failed = True
        if not self.error_code and not transport_failed:
            return True

        self.page_videos = cached_state["page_videos"]
        self.all_videos_cache = cached_state["all_videos_cache"]
        self.video_inventory = cached_state["video_inventory"]
        self.page_tokens = cached_state["page_tokens"]
        self.total_video_count = cached_state["total_video_count"]
        return False

    def set_channel_data(self, channel_response):
        """Extract channel information from API response"""
        if channel_response.get("items"):
            snippet = channel_response["items"][0]["snippet"]
            self.channel_thumbnail = best_thumbnail_url(
                snippet.get("thumbnails", {})
            )
            self.channel_name = snippet["title"]

    def get_total_video_count(self):
        """Get total number of videos in channel without fetching all video details"""
        try:
            playlist_response = self.youtube.playlists().list(
                id=self.uploads_id,
                part='contentDetails'
            ).execute()
            
            if playlist_response.get("items"):
                self.total_video_count = playlist_response["items"][0]["contentDetails"]["itemCount"]
            else:
                response = self.youtube.playlistItems().list(
                    playlistId=self.uploads_id,
                    part='id',
                    maxResults=1
                ).execute()
                self.total_video_count = response.get('pageInfo', {}).get('totalResults', 0)
                
        except googleapiclient.errors.HttpError as e:
            self.error_code = e.error_details[0]['reason']
            self.total_video_count = 0

    def set_video_filter(self, video_filter):
        """Select which kind of videos should be displayed."""
        self.video_filter = (
            video_filter if video_filter in VIDEO_FILTERS else "all"
        )

    def set_video_page(self, page):
        """Load and slice the selected video category for a specific page."""
        self.load_video_inventory()
        page = max(1, min(page, self.num_pages))
        self.current_page = page

        filtered_videos = self.filtered_videos
        if self.results_per_page == -1:
            self.page_videos = filtered_videos
            self.all_videos_cache = filtered_videos
        else:
            start = (page - 1) * self.results_per_page
            end = start + self.results_per_page
            self.page_videos = filtered_videos[start:end]
            self.all_videos_cache = []
        return page

    def load_video_inventory(self):
        """Load uploads and their durations/localizations in batches of 50."""
        if self.video_inventory:
            return

        playlist_items = []
        page_token = None

        try:
            while True:
                response = self.youtube.playlistItems().list(
                    playlistId=self.uploads_id,
                    part="snippet",
                    maxResults=50,
                    pageToken=page_token,
                ).execute(num_retries=1)
                playlist_items.extend(response.get("items", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            for start in range(0, len(playlist_items), 50):
                batch = playlist_items[start:start + 50]
                video_ids = [
                    item["snippet"]["resourceId"]["videoId"] for item in batch
                ]
                details_response = self.youtube.videos().list(
                    part="snippet,contentDetails,localizations",
                    id=",".join(video_ids),
                    maxResults=50,
                ).execute(num_retries=1)
                details_by_id = {
                    item["id"]: item for item in details_response.get("items", [])
                }

                for item in batch:
                    snippet = item["snippet"]
                    video_id = snippet["resourceId"]["videoId"]
                    details = details_by_id.get(video_id, {})
                    localizations = self._localization_codes(details)
                    default_language_code = normalize_language_code(
                        details.get("snippet", {}).get("defaultLanguage")
                    )
                    duration_seconds = parse_iso8601_duration(
                        details.get("contentDetails", {}).get("duration")
                    )
                    self.video_inventory.append(
                        Video(
                            snippet.get("title", "Untitled video"),
                            video_id,
                            snippet.get("description", ""),
                            best_thumbnail_url(snippet.get("thumbnails", {})),
                            localizations,
                            duration_seconds,
                            default_language_code=default_language_code,
                        )
                    )

            self.total_video_count = len(self.video_inventory)
        except googleapiclient.errors.HttpError as e:
            self.error_code = e.error_details[0]["reason"]

    @staticmethod
    def _localization_codes(video_data):
        localizations = list(video_data.get("localizations", {}).keys())
        return list(
            filter(None, {normalize_language_code(code) for code in localizations})
        )

    def refresh_video_language_metadata(self, videos):
        """Refresh source and localization languages for the selected videos."""
        videos_by_id = {video.id: video for video in videos}
        video_ids = list(videos_by_id)

        try:
            for start in range(0, len(video_ids), 50):
                response = self.youtube.videos().list(
                    part="snippet,localizations",
                    id=",".join(video_ids[start:start + 50]),
                    maxResults=50,
                ).execute()
                for item in response.get("items", []):
                    video = videos_by_id.get(item.get("id"))
                    if video is None:
                        continue
                    video.current_languages = self._localization_codes(item)
                    video.default_language_code = normalize_language_code(
                        item.get("snippet", {}).get("defaultLanguage")
                    )
                    video.default_language_name = self.code_to_name.get(
                        video.default_language_code
                    )
            return True
        except googleapiclient.errors.HttpError as exc:
            print(f"Error refreshing video languages: {exc}")
            self.error_code = exc.error_details[0]["reason"]
            return False

    def load_page_videos(self, page):
        """Load videos for a specific page efficiently"""
        try:
            page_token = self.get_page_token_for_page(page)
            
            videos_response = self.youtube.playlistItems().list(
                playlistId=self.uploads_id,
                part='snippet',
                maxResults=self.results_per_page,
                pageToken=page_token
            ).execute()

            if videos_response.get("nextPageToken"):
                self.page_tokens[page + 1] = videos_response["nextPageToken"]

            for item in videos_response["items"]:
                video_id = item["snippet"]["resourceId"]["videoId"]
                localizations = self.get_video_localizations(video_id)
                
                new_video = Video(
                    item["snippet"]["title"], 
                    video_id, 
                    item["snippet"]["description"],
                    best_thumbnail_url(item["snippet"].get("thumbnails", {})),
                    localizations
                )
                self.page_videos.append(new_video)
                
        except googleapiclient.errors.HttpError as e:
            self.error_code = e.error_details[0]['reason']

    def get_page_token_for_page(self, page):
        """Get the appropriate page token for a given page number"""
        if page == 1:
            return None
            
        if page in self.page_tokens:
            return self.page_tokens[page]
            
        current_page = 1
        page_token = None
        
        while current_page < page:
            response = self.youtube.playlistItems().list(
                playlistId=self.uploads_id,
                part='id',
                maxResults=self.results_per_page,
                pageToken=page_token
            ).execute()
            
            page_token = response.get("nextPageToken")
            current_page += 1
            
            if page_token:
                self.page_tokens[current_page] = page_token
            else:
                break
                
        return page_token

    def load_all_videos(self):
        """Load all videos when 'ALL' option is selected"""
        self.page_videos = []
        self.all_videos_cache = []
        page_token = None
        
        try:
            while True:
                videos_response = self.youtube.playlistItems().list(
                    playlistId=self.uploads_id,
                    part='snippet',
                    maxResults=50,
                    pageToken=page_token
                ).execute()

                for item in videos_response["items"]:
                    video_id = item["snippet"]["resourceId"]["videoId"]
                    localizations = self.get_video_localizations(video_id)
                    
                    new_video = Video(
                        item["snippet"]["title"], 
                        video_id, 
                        item["snippet"]["description"],
                        best_thumbnail_url(item["snippet"].get("thumbnails", {})),
                        localizations
                    )
                    self.page_videos.append(new_video)
                    self.all_videos_cache.append(new_video)

                page_token = videos_response.get("nextPageToken")
                if not page_token:
                    break
                    
        except googleapiclient.errors.HttpError as e:
            self.error_code = e.error_details[0]['reason']

    def set_uploads_id(self):
        """Get the uploads playlist ID for the authenticated channel"""
        try:
            channel_response = self.youtube.channels().list(
                part="snippet",
                mine=True
            ).execute()
            self.set_channel_data(channel_response)
            channel_id = channel_response["items"][0]["id"]
            uploads_response = self.youtube.channels().list(
                id=channel_id,
                part='contentDetails'
            ).execute()
            self.uploads_id = uploads_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        except googleapiclient.errors.HttpError as e:
            self.error_code = e.error_details[0]['reason']

    @staticmethod
    def _shorten_title(text, limit=100):
        """Shorten a title without splitting a word, reserving space for an ellipsis."""
        if len(text) <= limit:
            return text, False

        shortened = text[: limit - 1].rstrip()
        word_boundary = shortened.rfind(" ")
        if word_boundary > len(shortened) // 2:
            shortened = shortened[:word_boundary].rstrip()
        return f"{shortened}…", True

    @staticmethod
    def _shorten_description(text, limit=5000):
        """Shorten UTF-8 text at a character and preferably word boundary."""
        if len(text.encode("utf-8")) <= limit:
            return text, False

        ellipsis = "…"
        available_bytes = limit - len(ellipsis.encode("utf-8"))
        shortened = text.encode("utf-8")[:available_bytes].decode("utf-8", "ignore").rstrip()
        word_boundary = max(shortened.rfind(" "), shortened.rfind("\n"))
        if word_boundary > len(shortened) // 2:
            shortened = shortened[:word_boundary].rstrip()
        return f"{shortened}{ellipsis}", True

    def set_video_localization(self, video_id, language_code, language, title, description, trim_checked,
                               default_title):
        """Add or update localization for a video"""
        results = self.set_video_localizations(
            video_id,
            [
                {
                    "language_code": language_code,
                    "language": language,
                    "title": title,
                    "description": description,
                }
            ],
            trim_checked,
            default_title,
        )
        return bool(results and results[0]["outcome"] == "succeeded")

    def set_video_localizations(
        self,
        video_id,
        localizations,
        trim_checked,
        default_title,
    ):
        """Add or update multiple localizations with one YouTube write."""
        outcomes = []
        prepared = []
        for localization in localizations:
            language_code = localization["language_code"]
            language = localization["language"].strip()
            title = html.unescape(localization["title"].replace('\\n', '\n'))
            description = html.unescape(
                localization["description"].replace('\\n', '\n')
            )
            trimmed = False

            if not language_code:
                outcomes.append(
                    {
                        "outcome": "skipped",
                        "reason": "unknown_language",
                        "trimmed": False,
                    }
                )
                continue

            title_too_long = len(title) > 100
            description_too_long = len(description.encode("utf-8")) > 5000
            if trim_checked:
                title, title_trimmed = self._shorten_title(title)
                description, description_trimmed = self._shorten_description(
                    description
                )
                trimmed = title_trimmed or description_trimmed
                if trimmed:
                    self.videos_trimmed += 1
                    print(
                        f"Localization for video '{default_title}' → "
                        f"'{language}' was safely shortened"
                    )
            elif title_too_long or description_too_long:
                print(
                    f"Video '{default_title}' skipped for language "
                    f"'{language}' due to length."
                )
                outcomes.append(
                    {
                        "outcome": "skipped",
                        "reason": "text_too_long",
                        "trimmed": False,
                    }
                )
                continue

            outcome_index = len(outcomes)
            outcomes.append(None)
            prepared.append(
                {
                    "outcome_index": outcome_index,
                    "language_code": language_code,
                    "language": language,
                    "title": title,
                    "description": description,
                    "trimmed": trimmed,
                }
            )

        if not prepared:
            return outcomes

        print(
            f"Publishing {len(prepared)} localization(s) for "
            f"'{default_title}' in one YouTube update"
        )
        try:
            results = self.youtube.videos().list(
                part='snippet,localizations',
                id=video_id
            ).execute()
            video = results['items'][0]

            if 'defaultLanguage' not in video['snippet']:
                video['snippet']['defaultLanguage'] = 'en'

            if 'localizations' not in video:
                video['localizations'] = {}

            for localization in prepared:
                video['localizations'][localization["language_code"]] = {
                    'title': localization["title"],
                    'description': localization["description"],
                }

            self.youtube.videos().update(
                part='snippet,localizations',
                body=video
            ).execute()
            for localization in prepared:
                outcomes[localization["outcome_index"]] = {
                    "outcome": "succeeded",
                    "reason": None,
                    "trimmed": localization["trimmed"],
                }
        except googleapiclient.errors.HttpError as e:
            self.error_code = e.error_details[0]['reason']
            print(f"Error updating video: {e.error_details}")
            for localization in prepared:
                outcomes[localization["outcome_index"]] = {
                    "outcome": "failed",
                    "reason": "youtube_error",
                    "trimmed": localization["trimmed"],
                }
        return outcomes

    def get_video_localizations(self, video_id):
        """Get existing localizations for a video"""
        try:
            results = self.youtube.videos().list(
                part='localizations',
                id=video_id
            ).execute()
            
            if not results['items']:
                return []
            
            return self._localization_codes(results['items'][0])
            
        except googleapiclient.errors.HttpError as e:
            print(f"Error getting localizations for video {video_id}: {e}")
            return []


class Video:
    """Represents a YouTube video with translation data"""
    
    def __init__(
        self,
        title,
        vid_id,
        desc,
        thumb_url,
        curr_langs,
        duration_seconds=None,
        default_language_code=None,
    ):
        self.video_title = title
        self.id = vid_id
        self.description = desc
        self.thumbnail_url = thumb_url
        self.current_languages = curr_langs if curr_langs else []
        self.language_names = []
        self.duration_seconds = duration_seconds
        self.default_language_code = default_language_code
        self.default_language_name = None

    @property
    def is_short(self):
        return (
            self.duration_seconds is not None
            and self.duration_seconds <= SHORTS_MAX_DURATION_SECONDS
        )

    @property
    def num_languages(self):
        return len(self.current_languages)
