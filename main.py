# coding=utf-8

import json
import os
import random
import re
import time
import webbrowser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

import pytz
import requests
import yaml

try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False


VERSION = "3.4.1"


# === SMTP Email Configuration ===
SMTP_CONFIGS = {
    # Gmail (uses STARTTLS)
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "encryption": "TLS"},
    # QQ Mail (uses SSL, more stable)
    "qq.com": {"server": "smtp.qq.com", "port": 465, "encryption": "SSL"},
    # Outlook (uses STARTTLS)
    "outlook.com": {
        "server": "smtp-mail.outlook.com",
        "port": 587,
        "encryption": "TLS",
    },
    "hotmail.com": {
        "server": "smtp-mail.outlook.com",
        "port": 587,
        "encryption": "TLS",
    },
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    # NetEase Mail (uses SSL, more stable)
    "163.com": {"server": "smtp.163.com", "port": 465, "encryption": "SSL"},
    "126.com": {"server": "smtp.126.com", "port": 465, "encryption": "SSL"},
    # Sina Mail (uses SSL)
    "sina.com": {"server": "smtp.sina.com", "port": 465, "encryption": "SSL"},
    # Sohu Mail (uses SSL)
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "encryption": "SSL"},
    # Tianyi Mail (uses SSL)
    "189.cn": {"server": "smtp.189.cn", "port": 465, "encryption": "SSL"},
    # Aliyun Mail (uses TLS)
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "encryption": "TLS"},
}


# === Configuration Management ===
def load_config():
    """Load configuration file"""
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file {config_path} does not exist")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    print(f"Config file loaded successfully: {config_path}")

    # Build configuration
    config = {
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "REPORT_MODE": os.environ.get("REPORT_MODE", "").strip()
        or config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],
        "SORT_BY_POSITION_FIRST": os.environ.get("SORT_BY_POSITION_FIRST", "").strip().lower()
        in ("true", "1")
        if os.environ.get("SORT_BY_POSITION_FIRST", "").strip()
        else config_data["report"].get("sort_by_position_first", False),
        "MAX_NEWS_PER_KEYWORD": int(
            os.environ.get("MAX_NEWS_PER_KEYWORD", "").strip() or "0"
        )
        or config_data["report"].get("max_news_per_keyword", 0),
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": os.environ.get("ENABLE_CRAWLER", "").strip().lower()
        in ("true", "1")
        if os.environ.get("ENABLE_CRAWLER", "").strip()
        else config_data["crawler"]["enable_crawler"],
        "ENABLE_NOTIFICATION": os.environ.get("ENABLE_NOTIFICATION", "").strip().lower()
        in ("true", "1")
        if os.environ.get("ENABLE_NOTIFICATION", "").strip()
        else config_data["notification"]["enable_notification"],
        "MESSAGE_BATCH_SIZE": config_data["notification"]["message_batch_size"],
        "DINGTALK_BATCH_SIZE": config_data["notification"].get(
            "dingtalk_batch_size", 20000
        ),
        "FEISHU_BATCH_SIZE": config_data["notification"].get("feishu_batch_size", 29000),
        "BARK_BATCH_SIZE": config_data["notification"].get("bark_batch_size", 3600),
        "SLACK_BATCH_SIZE": config_data["notification"].get("slack_batch_size", 4000),
        "BATCH_SEND_INTERVAL": config_data["notification"]["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": config_data["notification"][
            "feishu_message_separator"
        ],
        "PUSH_WINDOW": {
            "ENABLED": os.environ.get("PUSH_WINDOW_ENABLED", "").strip().lower()
            in ("true", "1")
            if os.environ.get("PUSH_WINDOW_ENABLED", "").strip()
            else config_data["notification"]
            .get("push_window", {})
            .get("enabled", False),
            "TIME_RANGE": {
                "START": os.environ.get("PUSH_WINDOW_START", "").strip()
                or config_data["notification"]
                .get("push_window", {})
                .get("time_range", {})
                .get("start", "08:00"),
                "END": os.environ.get("PUSH_WINDOW_END", "").strip()
                or config_data["notification"]
                .get("push_window", {})
                .get("time_range", {})
                .get("end", "22:00"),
            },
            "ONCE_PER_DAY": os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip().lower()
            in ("true", "1")
            if os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip()
            else config_data["notification"]
            .get("push_window", {})
            .get("once_per_day", True),
            "RECORD_RETENTION_DAYS": int(
                os.environ.get("PUSH_WINDOW_RETENTION_DAYS", "").strip() or "0"
            )
            or config_data["notification"]
            .get("push_window", {})
            .get("push_record_retention_days", 7),
        },
        "WEIGHT_CONFIG": {
            "RANK_WEIGHT": config_data["weight"]["rank_weight"],
            "FREQUENCY_WEIGHT": config_data["weight"]["frequency_weight"],
            "HOTNESS_WEIGHT": config_data["weight"]["hotness_weight"],
        },
        "PLATFORMS": config_data["platforms"],
    }

    # Notification channel configuration (environment variables take priority)
    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})

    config["FEISHU_WEBHOOK_URL"] = os.environ.get(
        "FEISHU_WEBHOOK_URL", ""
    ).strip() or webhooks.get("feishu_url", "")
    config["DINGTALK_WEBHOOK_URL"] = os.environ.get(
        "DINGTALK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("dingtalk_url", "")
    config["WEWORK_WEBHOOK_URL"] = os.environ.get(
        "WEWORK_WEBHOOK_URL", ""
    ).strip() or webhooks.get("wework_url", "")
    config["WEWORK_MSG_TYPE"] = os.environ.get(
        "WEWORK_MSG_TYPE", ""
    ).strip() or webhooks.get("wework_msg_type", "markdown")
    config["TELEGRAM_BOT_TOKEN"] = os.environ.get(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip() or webhooks.get("telegram_bot_token", "")
    config["TELEGRAM_CHAT_ID"] = os.environ.get(
        "TELEGRAM_CHAT_ID", ""
    ).strip() or webhooks.get("telegram_chat_id", "")

    # Email configuration
    config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", "").strip() or webhooks.get(
        "email_from", ""
    )
    config["EMAIL_PASSWORD"] = os.environ.get(
        "EMAIL_PASSWORD", ""
    ).strip() or webhooks.get("email_password", "")
    config["EMAIL_TO"] = os.environ.get("EMAIL_TO", "").strip() or webhooks.get(
        "email_to", ""
    )
    config["EMAIL_SMTP_SERVER"] = os.environ.get(
        "EMAIL_SMTP_SERVER", ""
    ).strip() or webhooks.get("email_smtp_server", "")
    config["EMAIL_SMTP_PORT"] = os.environ.get(
        "EMAIL_SMTP_PORT", ""
    ).strip() or webhooks.get("email_smtp_port", "")

    # Resend config
    config["RESEND_API_KEY"] = os.environ.get(
        "RESEND_API_KEY", ""
    ).strip() or webhooks.get("resend_api_key", "")
    config["RESEND_FROM_EMAIL"] = os.environ.get(
        "RESEND_FROM_EMAIL", ""
    ).strip() or webhooks.get("resend_from_email", "")
    config["RESEND_TO_EMAIL"] = os.environ.get(
        "RESEND_TO_EMAIL", ""
    ).strip() or webhooks.get("resend_to_email", "")

    # ntfy configuration
    config["NTFY_SERVER_URL"] = (
        os.environ.get("NTFY_SERVER_URL", "").strip()
        or webhooks.get("ntfy_server_url")
        or "https://ntfy.sh"
    )
    config["NTFY_TOPIC"] = os.environ.get("NTFY_TOPIC", "").strip() or webhooks.get(
        "ntfy_topic", ""
    )
    config["NTFY_TOKEN"] = os.environ.get("NTFY_TOKEN", "").strip() or webhooks.get(
        "ntfy_token", ""
    )

    # Bark configuration
    config["BARK_URL"] = os.environ.get("BARK_URL", "").strip() or webhooks.get(
        "bark_url", ""
    )

    # Slack configuration
    config["SLACK_WEBHOOK_URL"] = os.environ.get("SLACK_WEBHOOK_URL", "").strip() or webhooks.get(
        "slack_webhook_url", ""
    )

    # Output configuration source info
    notification_sources = []
    if config["FEISHU_WEBHOOK_URL"]:
        source = "env" if os.environ.get("FEISHU_WEBHOOK_URL") else "config"
        notification_sources.append(f"Feishu({source})")
    if config["DINGTALK_WEBHOOK_URL"]:
        source = "env" if os.environ.get("DINGTALK_WEBHOOK_URL") else "config"
        notification_sources.append(f"DingTalk({source})")
    if config["WEWORK_WEBHOOK_URL"]:
        source = "env" if os.environ.get("WEWORK_WEBHOOK_URL") else "config"
        notification_sources.append(f"WeCom({source})")
    if config["TELEGRAM_BOT_TOKEN"] and config["TELEGRAM_CHAT_ID"]:
        token_source = (
            "env" if os.environ.get("TELEGRAM_BOT_TOKEN") else "config"
        )
        chat_source = "env" if os.environ.get("TELEGRAM_CHAT_ID") else "config"
        notification_sources.append(f"Telegram({token_source}/{chat_source})")
    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        from_source = "env" if os.environ.get("EMAIL_FROM") else "config"
        notification_sources.append(f"Email({from_source})")

    if config["RESEND_API_KEY"] and config["RESEND_FROM_EMAIL"] and config["RESEND_TO_EMAIL"]:
        resend_source = "env" if os.environ.get("RESEND_API_KEY") else "config"
        notification_sources.append(f"Resend({resend_source})")

    if config["NTFY_SERVER_URL"] and config["NTFY_TOPIC"]:
        server_source = "env" if os.environ.get("NTFY_SERVER_URL") else "config"
        notification_sources.append(f"ntfy({server_source})")

    if config["BARK_URL"]:
        bark_source = "env" if os.environ.get("BARK_URL") else "config"
        notification_sources.append(f"Bark({bark_source})")

    if config["SLACK_WEBHOOK_URL"]:
        slack_source = "env" if os.environ.get("SLACK_WEBHOOK_URL") else "config"
        notification_sources.append(f"Slack({slack_source})")

    if notification_sources:
        print(f"Notification channels: {', '.join(notification_sources)}")
    else:
        print("No notification channels configured")

    return config


print("Loading configuration...")
CONFIG = load_config()
print(f"TrendRadar v{VERSION} configuration loaded")
print(f"Monitored platforms: {len(CONFIG['PLATFORMS'])}")


# === Utility Functions ===
def get_beijing_time():
    """Get Beijing time"""
    return datetime.now(pytz.timezone("Asia/Shanghai"))


def format_date_folder():
    """Format date folder name"""
    return get_beijing_time().strftime("%Y-%m-%d")


def format_time_filename():
    """Format time filename"""
    return get_beijing_time().strftime("%H-%M")


def clean_title(title: str) -> str:
    """Clean special characters from title"""
    if not isinstance(title, str):
        title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    cleaned_title = cleaned_title.strip()
    return cleaned_title


def ensure_directory_exists(directory: str):
    """Ensure directory exists"""
    Path(directory).mkdir(parents=True, exist_ok=True)


def get_output_path(subfolder: str, filename: str) -> str:
    """Get output path"""
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / subfolder
    ensure_directory_exists(str(output_dir))
    return str(output_dir / filename)


def check_version_update(
    current_version: str, version_url: str, proxy_url: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """Check for version update"""
    try:
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/plain, */*",
            "Cache-Control": "no-cache",
        }

        response = requests.get(
            version_url, proxies=proxies, headers=headers, timeout=10
        )
        response.raise_for_status()

        remote_version = response.text.strip()
        print(f"Current version: {current_version}, Remote version: {remote_version}")

        # Compare versions
        def parse_version(version_str):
            try:
                parts = version_str.strip().split(".")
                if len(parts) != 3:
                    raise ValueError("Invalid version format")
                return int(parts[0]), int(parts[1]), int(parts[2])
            except:
                return 0, 0, 0

        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)

        need_update = current_tuple < remote_tuple
        return need_update, remote_version if need_update else None

    except Exception as e:
        print(f"Version check failed: {e}")
        return False, None


def is_first_crawl_today() -> bool:
    """Check if this is the first crawl today"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return True

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1


def html_escape(text: str) -> str:
    """Escape HTML special characters"""
    if not isinstance(text, str):
        text = str(text)

    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


# === Push Record Management ===
class PushRecordManager:
    """Push record manager"""

    def __init__(self):
        self.record_dir = Path("output") / ".push_records"
        self.ensure_record_dir()
        self.cleanup_old_records()

    def ensure_record_dir(self):
        """Ensure record directory exists"""
        self.record_dir.mkdir(parents=True, exist_ok=True)

    def get_today_record_file(self) -> Path:
        """Get today's record file path"""
        today = get_beijing_time().strftime("%Y%m%d")
        return self.record_dir / f"push_record_{today}.json"

    def cleanup_old_records(self):
        """Clean up expired push records"""
        retention_days = CONFIG["PUSH_WINDOW"]["RECORD_RETENTION_DAYS"]
        current_time = get_beijing_time()

        for record_file in self.record_dir.glob("push_record_*.json"):
            try:
                date_str = record_file.stem.replace("push_record_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")
                file_date = pytz.timezone("Asia/Shanghai").localize(file_date)

                if (current_time - file_date).days > retention_days:
                    record_file.unlink()
                    print(f"Cleaned expired push record: {record_file.name}")
            except Exception as e:
                print(f"Failed to clean record file {record_file}: {e}")

    def has_pushed_today(self) -> bool:
        """Check if already pushed today"""
        record_file = self.get_today_record_file()

        if not record_file.exists():
            return False

        try:
            with open(record_file, "r", encoding="utf-8") as f:
                record = json.load(f)
            return record.get("pushed", False)
        except Exception as e:
            print(f"Failed to read push record: {e}")
            return False

    def record_push(self, report_type: str):
        """Record push event"""
        record_file = self.get_today_record_file()
        now = get_beijing_time()

        record = {
            "pushed": True,
            "push_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": report_type,
        }

        try:
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            print(f"Push record saved: {report_type} at {now.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"Failed to save push record: {e}")

    def is_in_time_range(self, start_time: str, end_time: str) -> bool:
        """Check if current time is within specified time range"""
        now = get_beijing_time()
        current_time = now.strftime("%H:%M")

        def normalize_time(time_str: str) -> str:
            """Normalize time string to HH:MM format"""
            try:
                parts = time_str.strip().split(":")
                if len(parts) != 2:
                    raise ValueError(f"Invalid time format: {time_str}")

                hour = int(parts[0])
                minute = int(parts[1])

                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"Time out of range: {time_str}")

                return f"{hour:02d}:{minute:02d}"
            except Exception as e:
                print(f"Time format error '{time_str}': {e}")
                return time_str

        normalized_start = normalize_time(start_time)
        normalized_end = normalize_time(end_time)
        normalized_current = normalize_time(current_time)

        result = normalized_start <= normalized_current <= normalized_end

        if not result:
            print(f"Time window check: current {normalized_current}, window {normalized_start}-{normalized_end}")

        return result


# === Data Fetching ===
class DataFetcher:
    """Data fetcher"""

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """Fetch data for specified ID with retry support"""
        if isinstance(id_info, tuple):
            id_value, alias = id_info
        else:
            id_value = id_info
            alias = id_value

        url = f"https://newsnow.busiyi.world/api/s?id={id_value}&latest"

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url, proxies=proxies, headers=headers, timeout=10
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "unknown")
                if status not in ["success", "cache"]:
                    raise ValueError(f"Response status abnormal: {status}")

                status_info = "latest data" if status == "success" else "cached data"
                print(f"Fetched {id_value} successfully ({status_info})")
                return data_text, id_value, alias

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"Request {id_value} failed: {e}. Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Request {id_value} failed: {e}")
                    return None, id_value, alias
        return None, id_value, alias

    # === English Source Fetchers ===

    def fetch_hackernews(self) -> Tuple[Optional[str], str, str]:
        """Fetch top stories from Hacker News API (no auth required)"""
        id_value = "hackernews"
        alias = "Hacker News"

        try:
            # Get top story IDs
            top_stories_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            response = requests.get(top_stories_url, timeout=10)
            response.raise_for_status()
            story_ids = response.json()[:50]  # Get top 50

            items = []
            for idx, story_id in enumerate(story_ids):
                try:
                    item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                    item_response = requests.get(item_url, timeout=5)
                    item_data = item_response.json()

                    if item_data and item_data.get("title"):
                        items.append({
                            "title": item_data.get("title", ""),
                            "url": item_data.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                            "mobileUrl": f"https://news.ycombinator.com/item?id={story_id}",
                            "score": item_data.get("score", 0),
                        })

                    # Rate limit: small delay between requests
                    if idx < len(story_ids) - 1:
                        time.sleep(0.05)

                except Exception as e:
                    print(f"Failed to fetch HN item {story_id}: {e}")
                    continue

            result = {"status": "success", "items": items}
            print(f"Fetched {id_value} successfully ({len(items)} items)")
            return json.dumps(result), id_value, alias

        except Exception as e:
            print(f"Request {id_value} failed: {e}")
            return None, id_value, alias

    def fetch_google_trends(self) -> Tuple[Optional[str], str, str]:
        """Fetch trending searches from Google Trends via pytrends"""
        id_value = "googletrends"
        alias = "Google Trends"

        try:
            from pytrends.request import TrendReq

            pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))

            # Get trending searches for US
            trending_df = pytrends.trending_searches(pn='united_states')

            items = []
            for idx, row in trending_df.iterrows():
                keyword = row[0]
                items.append({
                    "title": keyword,
                    "url": f"https://trends.google.com/trends/explore?q={requests.utils.quote(keyword)}&geo=US",
                    "mobileUrl": f"https://trends.google.com/trends/explore?q={requests.utils.quote(keyword)}&geo=US",
                })

            result = {"status": "success", "items": items}
            print(f"Fetched {id_value} successfully ({len(items)} items)")
            return json.dumps(result), id_value, alias

        except ImportError:
            print(f"pytrends not installed. Run: pip install pytrends")
            return None, id_value, alias
        except Exception as e:
            print(f"Request {id_value} failed: {e}")
            return None, id_value, alias

    def fetch_reddit(self) -> Tuple[Optional[str], str, str]:
        """Fetch trending posts from Reddit (placeholder - requires OAuth setup)"""
        id_value = "reddit"
        alias = "Reddit Trending"

        # TODO: Implement Reddit OAuth flow
        # Requires: client_id, client_secret, username, password
        # Set these in environment variables:
        #   REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD

        print(f"Reddit API not configured. Set REDDIT_* environment variables.")
        print("See: https://www.reddit.com/prefs/apps to create an app")

        # Placeholder: return empty but valid response
        result = {"status": "success", "items": [
            {"title": "[Reddit not configured] Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET env vars", "url": "https://www.reddit.com/prefs/apps", "mobileUrl": ""}
        ]}
        return json.dumps(result), id_value, alias

    def fetch_producthunt(self) -> Tuple[Optional[str], str, str]:
        """Fetch top products from Product Hunt (placeholder - requires API token)"""
        id_value = "producthunt"
        alias = "Product Hunt"

        # TODO: Implement Product Hunt GraphQL API
        # Requires: developer_token from https://www.producthunt.com/v2/oauth/applications
        # Set in environment variable: PRODUCTHUNT_TOKEN

        print(f"Product Hunt API not configured. Set PRODUCTHUNT_TOKEN environment variable.")
        print("See: https://www.producthunt.com/v2/oauth/applications to get token")

        # Placeholder: return empty but valid response
        result = {"status": "success", "items": [
            {"title": "[Product Hunt not configured] Set PRODUCTHUNT_TOKEN env var", "url": "https://www.producthunt.com/v2/oauth/applications", "mobileUrl": ""}
        ]}
        return json.dumps(result), id_value, alias

    # === English Source Router ===
    ENGLISH_SOURCES = {
        "hackernews": "fetch_hackernews",
        "googletrends": "fetch_google_trends",
        "reddit": "fetch_reddit",
        "producthunt": "fetch_producthunt",
    }

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
    ) -> Tuple[Dict, Dict, List]:
        """Crawl multiple websites"""
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, id_info in enumerate(ids_list):
            if isinstance(id_info, tuple):
                id_value, name = id_info
            else:
                id_value = id_info
                name = id_value

            id_to_name[id_value] = name

            # Route to appropriate fetcher based on source type
            if id_value in self.ENGLISH_SOURCES:
                fetch_method = getattr(self, self.ENGLISH_SOURCES[id_value])
                response, _, _ = fetch_method()
            else:
                response, _, _ = self.fetch_data(id_info)

            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}
                    for index, item in enumerate(data.get("items", []), 1):
                        title = item.get("title")
                        # Skip invalid titles (None, float, empty strings)
                        if title is None or isinstance(title, float) or not str(title).strip():
                            continue
                        title = str(title).strip()
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")

                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                            }
                except json.JSONDecodeError:
                    print(f"Failed to parse {id_value} response")
                    failed_ids.append(id_value)
                except Exception as e:
                    print(f"Error processing {id_value} data: {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)

            if i < len(ids_list) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"Success: {list(results.keys())}, Failed: {failed_ids}")
        return results, id_to_name, failed_ids


# === Data Processing ===
def save_titles_to_file(results: Dict, id_to_name: Dict, failed_ids: List) -> str:
    """Save titles to file"""
    file_path = get_output_path("txt", f"{format_time_filename()}.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        for id_value, title_data in results.items():
            # id | name or just id
            name = id_to_name.get(id_value)
            if name and name != id_value:
                f.write(f"{id_value} | {name}\n")
            else:
                f.write(f"{id_value}\n")

            # Sort titles by rank
            sorted_titles = []
            for title, info in title_data.items():
                cleaned_title = clean_title(title)
                if isinstance(info, dict):
                    ranks = info.get("ranks", [])
                    url = info.get("url", "")
                    mobile_url = info.get("mobileUrl", "")
                else:
                    ranks = info if isinstance(info, list) else []
                    url = ""
                    mobile_url = ""

                rank = ranks[0] if ranks else 1
                sorted_titles.append((rank, cleaned_title, url, mobile_url))

            sorted_titles.sort(key=lambda x: x[0])

            for rank, cleaned_title, url, mobile_url in sorted_titles:
                line = f"{rank}. {cleaned_title}"

                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")

            f.write("\n")

        if failed_ids:
            f.write("==== Failed IDs ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")

    return file_path


def load_frequency_words(
    frequency_file: Optional[str] = None,
) -> Tuple[List[Dict], List[str]]:
    """Load frequency words configuration"""
    if frequency_file is None:
        frequency_file = os.environ.get(
            "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
        )

    frequency_path = Path(frequency_file)
    if not frequency_path.exists():
        raise FileNotFoundError(f"Frequency words file {frequency_file} does not exist")

    with open(frequency_path, "r", encoding="utf-8") as f:
        content = f.read()

    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]

    processed_groups = []
    filter_words = []

    for group in word_groups:
        words = [word.strip() for word in group.split("\n") if word.strip()]

        group_required_words = []
        group_normal_words = []
        group_filter_words = []
        group_max_count = 0  # Default: no limit

        for word in words:
            if word.startswith("@"):
                # Parse max display count (only positive integers)
                try:
                    count = int(word[1:])
                    if count > 0:
                        group_max_count = count
                except (ValueError, IndexError):
                    pass  # Ignore invalid @ number format
            elif word.startswith("!"):
                filter_words.append(word[1:])
                group_filter_words.append(word[1:])
            elif word.startswith("+"):
                group_required_words.append(word[1:])
            else:
                group_normal_words.append(word)

        if group_required_words or group_normal_words:
            if group_normal_words:
                group_key = " ".join(group_normal_words)
            else:
                group_key = " ".join(group_required_words)

            processed_groups.append(
                {
                    "required": group_required_words,
                    "normal": group_normal_words,
                    "group_key": group_key,
                    "max_count": group_max_count,  # Added field
                }
            )

    return processed_groups, filter_words


def parse_file_titles(file_path: Path) -> Tuple[Dict, Dict]:
    """Parse title data from a single txt file, returns (titles_by_id, id_to_name)"""
    titles_by_id = {}
    id_to_name = {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        sections = content.split("\n\n")

        for section in sections:
            if not section.strip() or "==== Failed IDs ====" in section:
                continue

            lines = section.strip().split("\n")
            if len(lines) < 2:
                continue

            # id | name or just id
            header_line = lines[0].strip()
            if " | " in header_line:
                parts = header_line.split(" | ", 1)
                source_id = parts[0].strip()
                name = parts[1].strip()
                id_to_name[source_id] = name
            else:
                source_id = header_line
                id_to_name[source_id] = source_id

            titles_by_id[source_id] = {}

            for line in lines[1:]:
                if line.strip():
                    try:
                        title_part = line.strip()
                        rank = None

                        # Extract rank
                        if ". " in title_part and title_part.split(". ")[0].isdigit():
                            rank_str, title_part = title_part.split(". ", 1)
                            rank = int(rank_str)

                        # Extract MOBILE URL
                        mobile_url = ""
                        if " [MOBILE:" in title_part:
                            title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                            if mobile_part.endswith("]"):
                                mobile_url = mobile_part[:-1]

                        # Extract URL
                        url = ""
                        if " [URL:" in title_part:
                            title_part, url_part = title_part.rsplit(" [URL:", 1)
                            if url_part.endswith("]"):
                                url = url_part[:-1]

                        title = clean_title(title_part.strip())
                        ranks = [rank] if rank is not None else [1]

                        titles_by_id[source_id][title] = {
                            "ranks": ranks,
                            "url": url,
                            "mobileUrl": mobile_url,
                        }

                    except Exception as e:
                        print(f"Error parsing title line: {line}, error: {e}")

    return titles_by_id, id_to_name


def read_all_today_titles(
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """Read all title files for today, with optional platform filtering"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return {}, {}, {}

    all_results = {}
    final_id_to_name = {}
    title_info = {}

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])

    for file_path in files:
        time_info = file_path.stem

        titles_by_id, file_id_to_name = parse_file_titles(file_path)

        if current_platform_ids is not None:
            filtered_titles_by_id = {}
            filtered_id_to_name = {}

            for source_id, title_data in titles_by_id.items():
                if source_id in current_platform_ids:
                    filtered_titles_by_id[source_id] = title_data
                    if source_id in file_id_to_name:
                        filtered_id_to_name[source_id] = file_id_to_name[source_id]

            titles_by_id = filtered_titles_by_id
            file_id_to_name = filtered_id_to_name

        final_id_to_name.update(file_id_to_name)

        for source_id, title_data in titles_by_id.items():
            process_source_data(
                source_id, title_data, time_info, all_results, title_info
            )

    return all_results, final_id_to_name, title_info


def process_source_data(
    source_id: str,
    title_data: Dict,
    time_info: str,
    all_results: Dict,
    title_info: Dict,
) -> None:
    """Process source data, merge duplicate titles"""
    if source_id not in all_results:
        all_results[source_id] = title_data

        if source_id not in title_info:
            title_info[source_id] = {}

        for title, data in title_data.items():
            ranks = data.get("ranks", [])
            url = data.get("url", "")
            mobile_url = data.get("mobileUrl", "")

            title_info[source_id][title] = {
                "first_time": time_info,
                "last_time": time_info,
                "count": 1,
                "ranks": ranks,
                "url": url,
                "mobileUrl": mobile_url,
            }
    else:
        for title, data in title_data.items():
            ranks = data.get("ranks", [])
            url = data.get("url", "")
            mobile_url = data.get("mobileUrl", "")

            if title not in all_results[source_id]:
                all_results[source_id][title] = {
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
            else:
                existing_data = all_results[source_id][title]
                existing_ranks = existing_data.get("ranks", [])
                existing_url = existing_data.get("url", "")
                existing_mobile_url = existing_data.get("mobileUrl", "")

                merged_ranks = existing_ranks.copy()
                for rank in ranks:
                    if rank not in merged_ranks:
                        merged_ranks.append(rank)

                all_results[source_id][title] = {
                    "ranks": merged_ranks,
                    "url": existing_url or url,
                    "mobileUrl": existing_mobile_url or mobile_url,
                }

                title_info[source_id][title]["last_time"] = time_info
                title_info[source_id][title]["ranks"] = merged_ranks
                title_info[source_id][title]["count"] += 1
                if not title_info[source_id][title].get("url"):
                    title_info[source_id][title]["url"] = url
                if not title_info[source_id][title].get("mobileUrl"):
                    title_info[source_id][title]["mobileUrl"] = mobile_url


def detect_latest_new_titles(current_platform_ids: Optional[List[str]] = None) -> Dict:
    """Detect new titles from the latest batch today, with optional platform filtering"""
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"

    if not txt_dir.exists():
        return {}

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    if len(files) < 2:
        return {}

    # Parse latest file
    latest_file = files[-1]
    latest_titles, _ = parse_file_titles(latest_file)

    # Filter latest file data if platform list is specified
    if current_platform_ids is not None:
        filtered_latest_titles = {}
        for source_id, title_data in latest_titles.items():
            if source_id in current_platform_ids:
                filtered_latest_titles[source_id] = title_data
        latest_titles = filtered_latest_titles

    # Aggregate historical titles (filtered by platform)
    historical_titles = {}
    for file_path in files[:-1]:
        historical_data, _ = parse_file_titles(file_path)

        # Filter historical data
        if current_platform_ids is not None:
            filtered_historical_data = {}
            for source_id, title_data in historical_data.items():
                if source_id in current_platform_ids:
                    filtered_historical_data[source_id] = title_data
            historical_data = filtered_historical_data

        for source_id, titles_data in historical_data.items():
            if source_id not in historical_titles:
                historical_titles[source_id] = set()
            for title in titles_data.keys():
                historical_titles[source_id].add(title)

    # Find new titles
    new_titles = {}
    for source_id, latest_source_titles in latest_titles.items():
        historical_set = historical_titles.get(source_id, set())
        source_new_titles = {}

        for title, title_data in latest_source_titles.items():
            if title not in historical_set:
                source_new_titles[title] = title_data

        if source_new_titles:
            new_titles[source_id] = source_new_titles

    return new_titles


# === Statistics and Analysis ===
def calculate_news_weight(
    title_data: Dict, rank_threshold: int = CONFIG["RANK_THRESHOLD"]
) -> float:
    """Calculate news weight for sorting"""
    ranks = title_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = title_data.get("count", len(ranks))
    weight_config = CONFIG["WEIGHT_CONFIG"]

    # Rank weight: Σ(11 - min(rank, 10)) / occurrence count
    rank_scores = []
    for rank in ranks:
        score = 11 - min(rank, 10)
        rank_scores.append(score)

    rank_weight = sum(rank_scores) / len(ranks) if ranks else 0

    # Frequency weight: min(occurrence count, 10) × 10
    frequency_weight = min(count, 10) * 10

    # Hotness bonus: high rank count / total occurrence count × 100
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_ratio = high_rank_count / len(ranks) if ranks else 0
    hotness_weight = hotness_ratio * 100

    total_weight = (
        rank_weight * weight_config["RANK_WEIGHT"]
        + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
        + hotness_weight * weight_config["HOTNESS_WEIGHT"]
    )

    return total_weight


def matches_word_groups(
    title: str, word_groups: List[Dict], filter_words: List[str]
) -> bool:
    """Check if title matches word group rules"""
    # Defensive type check: ensure title is a valid string
    if not isinstance(title, str):
        title = str(title) if title is not None else ""
    if not title.strip():
        return False

    # If no word groups configured, match all titles (show all news)
    if not word_groups:
        return True

    title_lower = title.lower()

    # Filter words check
    if any(filter_word.lower() in title_lower for filter_word in filter_words):
        return False

    # Word group matching check
    for group in word_groups:
        required_words = group["required"]
        normal_words = group["normal"]

        # Required words check
        if required_words:
            all_required_present = all(
                req_word.lower() in title_lower for req_word in required_words
            )
            if not all_required_present:
                continue

        # Normal words check
        if normal_words:
            any_normal_present = any(
                normal_word.lower() in title_lower for normal_word in normal_words
            )
            if not any_normal_present:
                continue

        return True

    return False


def format_time_display(first_time: str, last_time: str) -> str:
    """Format time display"""
    if not first_time:
        return ""
    if first_time == last_time or not last_time:
        return first_time
    else:
        return f"[{first_time} ~ {last_time}]"


def format_rank_display(ranks: List[int], rank_threshold: int, format_type: str) -> str:
    """Unified rank formatting method"""
    if not ranks:
        return ""

    unique_ranks = sorted(set(ranks))
    min_rank = unique_ranks[0]
    max_rank = unique_ranks[-1]

    if format_type == "html":
        highlight_start = "<font color='red'><strong>"
        highlight_end = "</strong></font>"
    elif format_type == "feishu":
        highlight_start = "<font color='red'>**"
        highlight_end = "**</font>"
    elif format_type == "dingtalk":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "wework":
        highlight_start = "**"
        highlight_end = "**"
    elif format_type == "telegram":
        highlight_start = "<b>"
        highlight_end = "</b>"
    elif format_type == "slack":
        highlight_start = "*"
        highlight_end = "*"
    else:
        highlight_start = "**"
        highlight_end = "**"

    if min_rank <= rank_threshold:
        if min_rank == max_rank:
            return f"{highlight_start}[{min_rank}]{highlight_end}"
        else:
            return f"{highlight_start}[{min_rank} - {max_rank}]{highlight_end}"
    else:
        if min_rank == max_rank:
            return f"[{min_rank}]"
        else:
            return f"[{min_rank} - {max_rank}]"


def count_word_frequency(
    results: Dict,
    word_groups: List[Dict],
    filter_words: List[str],
    id_to_name: Dict,
    title_info: Optional[Dict] = None,
    rank_threshold: int = CONFIG["RANK_THRESHOLD"],
    new_titles: Optional[Dict] = None,
    mode: str = "daily",
) -> Tuple[List[Dict], int]:
    """Count word frequency, supporting required words, frequency words, filter words, and marking new titles"""

    # If no word groups configured, create a virtual group containing all news
    if not word_groups:
        print("Frequency words config is empty, showing all news")
        word_groups = [{"required": [], "normal": [], "group_key": "All News"}]
        filter_words = []  # Clear filter words, show all news

    is_first_today = is_first_crawl_today()

    # Determine data source and new title marking logic
    if mode == "incremental":
        if is_first_today:
            # Incremental mode + first crawl today: process all news, mark all as new
            results_to_process = results
            all_news_are_new = True
        else:
            # Incremental mode + not first crawl today: only process new news
            results_to_process = new_titles if new_titles else {}
            all_news_are_new = True
    elif mode == "current":
        # Current mode: only process news from current time batch, but stats from full history
        if title_info:
            latest_time = None
            for source_titles in title_info.values():
                for title_data in source_titles.values():
                    last_time = title_data.get("last_time", "")
                    if last_time:
                        if latest_time is None or last_time > latest_time:
                            latest_time = last_time

            # Only process news where last_time equals latest time
            if latest_time:
                results_to_process = {}
                for source_id, source_titles in results.items():
                    if source_id in title_info:
                        filtered_titles = {}
                        for title, title_data in source_titles.items():
                            if title in title_info[source_id]:
                                info = title_info[source_id][title]
                                if info.get("last_time") == latest_time:
                                    filtered_titles[title] = title_data
                        if filtered_titles:
                            results_to_process[source_id] = filtered_titles

                print(
                    f"Current ranking mode: latest time {latest_time}, filtered {sum(len(titles) for titles in results_to_process.values())} current ranking news"
                )
            else:
                results_to_process = results
        else:
            results_to_process = results
        all_news_are_new = False
    else:
        # Daily summary mode: process all news
        results_to_process = results
        all_news_are_new = False
        total_input_news = sum(len(titles) for titles in results.values())
        filter_status = (
            "show all"
            if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
            else "keyword filter"
        )
        print(f"Daily summary mode: processing {total_input_news} news, mode: {filter_status}")

    word_stats = {}
    total_titles = 0
    processed_titles = {}
    matched_new_count = 0

    if title_info is None:
        title_info = {}
    if new_titles is None:
        new_titles = {}

    for group in word_groups:
        group_key = group["group_key"]
        word_stats[group_key] = {"count": 0, "titles": {}}

    for source_id, titles_data in results_to_process.items():
        total_titles += len(titles_data)

        if source_id not in processed_titles:
            processed_titles[source_id] = {}

        for title, title_data in titles_data.items():
            if title in processed_titles.get(source_id, {}):
                continue

            # Use unified matching logic
            matches_frequency_words = matches_word_groups(
                title, word_groups, filter_words
            )

            if not matches_frequency_words:
                continue

            # If incremental mode or first crawl in current mode, count matching new news
            if (mode == "incremental" and all_news_are_new) or (
                mode == "current" and is_first_today
            ):
                matched_new_count += 1

            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")

            # Find matching word group (defensive conversion ensures type safety)
            title_lower = str(title).lower() if not isinstance(title, str) else title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]

                # If "All News" mode, all titles match the first (only) word group
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News":
                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []
                else:
                    # Original matching logic
                    if required_words:
                        all_required_present = all(
                            req_word.lower() in title_lower
                            for req_word in required_words
                        )
                        if not all_required_present:
                            continue

                    if normal_words:
                        any_normal_present = any(
                            normal_word.lower() in title_lower
                            for normal_word in normal_words
                        )
                        if not any_normal_present:
                            continue

                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []

                first_time = ""
                last_time = ""
                count_info = 1
                ranks = source_ranks if source_ranks else []
                url = source_url
                mobile_url = source_mobile_url

                # For current mode, get complete data from historical stats
                if (
                    mode == "current"
                    and title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)
                elif (
                    title_info
                    and source_id in title_info
                    and title in title_info[source_id]
                ):
                    info = title_info[source_id][title]
                    first_time = info.get("first_time", "")
                    last_time = info.get("last_time", "")
                    count_info = info.get("count", 1)
                    if "ranks" in info and info["ranks"]:
                        ranks = info["ranks"]
                    url = info.get("url", source_url)
                    mobile_url = info.get("mobileUrl", source_mobile_url)

                if not ranks:
                    ranks = [99]

                time_display = format_time_display(first_time, last_time)

                source_name = id_to_name.get(source_id, source_id)

                # Determine if news is new
                is_new = False
                if all_news_are_new:
                    # In incremental mode all processed news is new, or all news on first crawl is new
                    is_new = True
                elif new_titles and source_id in new_titles:
                    # Check if in new titles list
                    new_titles_for_source = new_titles[source_id]
                    is_new = title in new_titles_for_source

                word_stats[group_key]["titles"][source_id].append(
                    {
                        "title": title,
                        "source_name": source_name,
                        "first_time": first_time,
                        "last_time": last_time,
                        "time_display": time_display,
                        "count": count_info,
                        "ranks": ranks,
                        "rank_threshold": rank_threshold,
                        "url": url,
                        "mobileUrl": mobile_url,
                        "is_new": is_new,
                    }
                )

                if source_id not in processed_titles:
                    processed_titles[source_id] = {}
                processed_titles[source_id][title] = True

                break

    # Print summary info at the end
    if mode == "incremental":
        if is_first_today:
            total_input_news = sum(len(titles) for titles in results.values())
            filter_status = (
                "show all"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
                else "keyword match"
            )
            print(
                f"Incremental mode: first crawl today, {matched_new_count} out of {total_input_news} news {filter_status}"
            )
        else:
            if new_titles:
                total_new_count = sum(len(titles) for titles in new_titles.values())
                filter_status = (
                    "show all"
                    if len(word_groups) == 1
                    and word_groups[0]["group_key"] == "All News"
                    else "matched keywords"
                )
                print(
                    f"Incremental mode: {matched_new_count} out of {total_new_count} new news {filter_status}"
                )
                if matched_new_count == 0 and len(word_groups) > 1:
                    print("Incremental mode: no new news matched keywords, notification will not be sent")
            else:
                print("Incremental mode: no new news detected")
    elif mode == "current":
        total_input_news = sum(len(titles) for titles in results_to_process.values())
        if is_first_today:
            filter_status = (
                "show all"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
                else "keyword match"
            )
            print(
                f"Current ranking mode: first crawl today, {matched_new_count} out of {total_input_news} current ranking news {filter_status}"
            )
        else:
            matched_count = sum(stat["count"] for stat in word_stats.values())
            filter_status = (
                "show all"
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "All News"
                else "keyword match"
            )
            print(
                f"Current ranking mode: {matched_count} out of {total_input_news} current ranking news {filter_status}"
            )

    stats = []
    # Create group_key to position and max count mapping
    group_key_to_position = {
        group["group_key"]: idx for idx, group in enumerate(word_groups)
    }
    group_key_to_max_count = {
        group["group_key"]: group.get("max_count", 0) for group in word_groups
    }

    for group_key, data in word_stats.items():
        all_titles = []
        for source_id, title_list in data["titles"].items():
            all_titles.extend(title_list)

        # Sort by weight
        sorted_titles = sorted(
            all_titles,
            key=lambda x: (
                -calculate_news_weight(x, rank_threshold),
                min(x["ranks"]) if x["ranks"] else 999,
                -x["count"],
            ),
        )

        # Apply max display count limit (priority: group config > global config)
        group_max_count = group_key_to_max_count.get(group_key, 0)
        if group_max_count == 0:
            # Use global config
            group_max_count = CONFIG.get("MAX_NEWS_PER_KEYWORD", 0)

        if group_max_count > 0:
            sorted_titles = sorted_titles[:group_max_count]

        stats.append(
            {
                "word": group_key,
                "count": data["count"],
                "position": group_key_to_position.get(group_key, 999),
                "titles": sorted_titles,
                "percentage": (
                    round(data["count"] / total_titles * 100, 2)
                    if total_titles > 0
                    else 0
                ),
            }
        )

    # Choose sorting priority based on config
    if CONFIG.get("SORT_BY_POSITION_FIRST", False):
        # Sort by config position first, then by hot news count
        stats.sort(key=lambda x: (x["position"], -x["count"]))
    else:
        # Sort by hot news count first, then by config position (original logic)
        stats.sort(key=lambda x: (-x["count"], x["position"]))

    return stats, total_titles


# === Report Generation ===
def prepare_report_data(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
) -> Dict:
    """Prepare report data"""
    processed_new_titles = []

    # Hide new news section in incremental mode
    hide_new_section = mode == "incremental"

    # Only process new news section when not hidden
    if not hide_new_section:
        filtered_new_titles = {}
        if new_titles and id_to_name:
            word_groups, filter_words = load_frequency_words()
            for source_id, titles_data in new_titles.items():
                filtered_titles = {}
                for title, title_data in titles_data.items():
                    if matches_word_groups(title, word_groups, filter_words):
                        filtered_titles[title] = title_data
                if filtered_titles:
                    filtered_new_titles[source_id] = filtered_titles

        if filtered_new_titles and id_to_name:
            for source_id, titles_data in filtered_new_titles.items():
                source_name = id_to_name.get(source_id, source_id)
                source_titles = []

                for title, title_data in titles_data.items():
                    url = title_data.get("url", "")
                    mobile_url = title_data.get("mobileUrl", "")
                    ranks = title_data.get("ranks", [])

                    processed_title = {
                        "title": title,
                        "source_name": source_name,
                        "time_display": "",
                        "count": 1,
                        "ranks": ranks,
                        "rank_threshold": CONFIG["RANK_THRESHOLD"],
                        "url": url,
                        "mobile_url": mobile_url,
                        "is_new": True,
                    }
                    source_titles.append(processed_title)

                if source_titles:
                    processed_new_titles.append(
                        {
                            "source_id": source_id,
                            "source_name": source_name,
                            "titles": source_titles,
                        }
                    )

    processed_stats = []
    for stat in stats:
        if stat["count"] <= 0:
            continue

        processed_titles = []
        for title_data in stat["titles"]:
            processed_title = {
                "title": title_data["title"],
                "source_name": title_data["source_name"],
                "time_display": title_data["time_display"],
                "count": title_data["count"],
                "ranks": title_data["ranks"],
                "rank_threshold": title_data["rank_threshold"],
                "url": title_data.get("url", ""),
                "mobile_url": title_data.get("mobileUrl", ""),
                "is_new": title_data.get("is_new", False),
            }
            processed_titles.append(processed_title)

        processed_stats.append(
            {
                "word": stat["word"],
                "count": stat["count"],
                "percentage": stat.get("percentage", 0),
                "titles": processed_titles,
            }
        )

    return {
        "stats": processed_stats,
        "new_titles": processed_new_titles,
        "failed_ids": failed_ids or [],
        "total_new_count": sum(
            len(source["titles"]) for source in processed_new_titles
        ),
    }


def format_title_for_platform(
    platform: str, title_data: Dict, show_source: bool = True
) -> str:
    """Unified title formatting method for different platforms"""
    rank_display = format_rank_display(
        title_data["ranks"], title_data["rank_threshold"], platform
    )

    link_url = title_data["mobile_url"] or title_data["url"]

    cleaned_title = clean_title(title_data["title"])

    if platform == "feishu":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']} times)</font>"

        return result

    elif platform == "dingtalk":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']} times)"

        return result

    elif platform in ("wework", "bark"):
        # WeWork and Bark use markdown format
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']} times)"

        return result

    elif platform == "telegram":
        if link_url:
            formatted_title = f'<a href="{link_url}">{html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}times)</code>"

        return result

    elif platform == "ntfy":
        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}times)`"

        return result

    elif platform == "slack":
        # Slack uses mrkdwn format
        if link_url:
            # Slack link format: <url|text>
            formatted_title = f"<{link_url}|{cleaned_title}>"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data.get("is_new") else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        # Rank (using * for bold)
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "slack"
        )
        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" `- {title_data['time_display']}`"
        if title_data["count"] > 1:
            result += f" `({title_data['count']}times)`"

        return result

    elif platform == "html":
        rank_display = format_rank_display(
            title_data["ranks"], title_data["rank_threshold"], "html"
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        escaped_title = html_escape(cleaned_title)
        escaped_source_name = html_escape(title_data["source_name"])

        if link_url:
            escaped_url = html_escape(link_url)
            formatted_title = f'[{escaped_source_name}] <a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = (
                f'[{escaped_source_name}] <span class="no-link">{escaped_title}</span>'
            )

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}times)</font>"

        if title_data.get("is_new"):
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    else:
        return cleaned_title


def generate_html_report(
    stats: List[Dict],
    total_titles: int,
    failed_ids: Optional[List] = None,
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    mode: str = "daily",
    is_daily_summary: bool = False,
    update_info: Optional[Dict] = None,
) -> str:
    """Generate HTML report"""
    if is_daily_summary:
        if mode == "current":
            filename = "current_ranking.html"
        elif mode == "incremental":
            filename = "daily_incremental.html"
        else:
            filename = "daily_summary.html"
    else:
        filename = f"{format_time_filename()}.html"

    file_path = get_output_path("html", filename)

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)

    html_content = render_html_content(
        report_data, total_titles, is_daily_summary, mode, update_info
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if is_daily_summary:
        root_file_path = Path("index.html")
        with open(root_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    return file_path


def render_html_content(
    report_data: Dict,
    total_titles: int,
    is_daily_summary: bool = False,
    mode: str = "daily",
    update_info: Optional[Dict] = None,
) -> str:
    """Render HTML content"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hot News Analysis</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js" integrity="sha512-BNaRQnYJYiPSqHHDb58B0yaPfCu+Wgds8Gp/gU33kqBtgNS4tSPHuGibyoeqMV/TJlSKda6FXzoEyYGjTe+vXA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
                margin: 0; 
                padding: 16px; 
                background: #fafafa;
                color: #333;
                line-height: 1.5;
            }
            
            .container {
                max-width: 600px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 2px 16px rgba(0,0,0,0.06);
            }
            
            .header {
                background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
                color: white;
                padding: 32px 24px;
                text-align: center;
                position: relative;
            }
            
            .save-buttons {
                position: absolute;
                top: 16px;
                right: 16px;
                display: flex;
                gap: 8px;
            }
            
            .save-btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s ease;
                backdrop-filter: blur(10px);
                white-space: nowrap;
            }
            
            .save-btn:hover {
                background: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.5);
                transform: translateY(-1px);
            }
            
            .save-btn:active {
                transform: translateY(0);
            }
            
            .save-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            
            .header-title {
                font-size: 22px;
                font-weight: 700;
                margin: 0 0 20px 0;
            }
            
            .header-info {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                font-size: 14px;
                opacity: 0.95;
            }
            
            .info-item {
                text-align: center;
            }
            
            .info-label {
                display: block;
                font-size: 12px;
                opacity: 0.8;
                margin-bottom: 4px;
            }
            
            .info-value {
                font-weight: 600;
                font-size: 16px;
            }
            
            .content {
                padding: 24px;
            }
            
            .word-group {
                margin-bottom: 40px;
            }
            
            .word-group:first-child {
                margin-top: 0;
            }
            
            .word-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 20px;
                padding-bottom: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            
            .word-info {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .word-name {
                font-size: 17px;
                font-weight: 600;
                color: #1a1a1a;
            }
            
            .word-count {
                color: #666;
                font-size: 13px;
                font-weight: 500;
            }
            
            .word-count.hot { color: #dc2626; font-weight: 600; }
            .word-count.warm { color: #ea580c; font-weight: 600; }
            
            .word-index {
                color: #999;
                font-size: 12px;
            }
            
            .news-item {
                margin-bottom: 20px;
                padding: 16px 0;
                border-bottom: 1px solid #f5f5f5;
                position: relative;
                display: flex;
                gap: 12px;
                align-items: center;
            }
            
            .news-item:last-child {
                border-bottom: none;
            }
            
            .news-item.new::after {
                content: "NEW";
                position: absolute;
                top: 12px;
                right: 0;
                background: #fbbf24;
                color: #92400e;
                font-size: 9px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 4px;
                letter-spacing: 0.5px;
            }
            
            .news-number {
                color: #999;
                font-size: 13px;
                font-weight: 600;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 24px;
                height: 24px;
                display: flex;
                align-items: center;
                justify-content: center;
                align-self: flex-start;
                margin-top: 8px;
            }
            
            .news-content {
                flex: 1;
                min-width: 0;
                padding-right: 40px;
            }
            
            .news-item.new .news-content {
                padding-right: 50px;
            }
            
            .news-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
                flex-wrap: wrap;
            }
            
            .source-name {
                color: #666;
                font-size: 12px;
                font-weight: 500;
            }
            
            .rank-num {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 10px;
                min-width: 18px;
                text-align: center;
            }
            
            .rank-num.top { background: #dc2626; }
            .rank-num.high { background: #ea580c; }
            
            .time-info {
                color: #999;
                font-size: 11px;
            }
            
            .count-info {
                color: #059669;
                font-size: 11px;
                font-weight: 500;
            }
            
            .news-title {
                font-size: 15px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }
            
            .news-link {
                color: #2563eb;
                text-decoration: none;
            }
            
            .news-link:hover {
                text-decoration: underline;
            }
            
            .news-link:visited {
                color: #7c3aed;
            }
            
            .new-section {
                margin-top: 40px;
                padding-top: 24px;
                border-top: 2px solid #f0f0f0;
            }
            
            .new-section-title {
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                margin: 0 0 20px 0;
            }
            
            .new-source-group {
                margin-bottom: 24px;
            }
            
            .new-source-title {
                color: #666;
                font-size: 13px;
                font-weight: 500;
                margin: 0 0 12px 0;
                padding-bottom: 6px;
                border-bottom: 1px solid #f5f5f5;
            }
            
            .new-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 8px 0;
                border-bottom: 1px solid #f9f9f9;
            }
            
            .new-item:last-child {
                border-bottom: none;
            }
            
            .new-item-number {
                color: #999;
                font-size: 12px;
                font-weight: 600;
                min-width: 18px;
                text-align: center;
                flex-shrink: 0;
                background: #f8f9fa;
                border-radius: 50%;
                width: 20px;
                height: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .new-item-rank {
                color: #fff;
                background: #6b7280;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 6px;
                border-radius: 8px;
                min-width: 20px;
                text-align: center;
                flex-shrink: 0;
            }
            
            .new-item-rank.top { background: #dc2626; }
            .new-item-rank.high { background: #ea580c; }
            
            .new-item-content {
                flex: 1;
                min-width: 0;
            }
            
            .new-item-title {
                font-size: 14px;
                line-height: 1.4;
                color: #1a1a1a;
                margin: 0;
            }
            
            .error-section {
                background: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }
            
            .error-title {
                color: #dc2626;
                font-size: 14px;
                font-weight: 600;
                margin: 0 0 8px 0;
            }
            
            .error-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            
            .error-item {
                color: #991b1b;
                font-size: 13px;
                padding: 2px 0;
                font-family: 'SF Mono', Consolas, monospace;
            }
            
            .footer {
                margin-top: 32px;
                padding: 20px 24px;
                background: #f8f9fa;
                border-top: 1px solid #e5e7eb;
                text-align: center;
            }
            
            .footer-content {
                font-size: 13px;
                color: #6b7280;
                line-height: 1.6;
            }
            
            .footer-link {
                color: #4f46e5;
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s ease;
            }
            
            .footer-link:hover {
                color: #7c3aed;
                text-decoration: underline;
            }
            
            .project-name {
                font-weight: 600;
                color: #374151;
            }
            
            @media (max-width: 480px) {
                body { padding: 12px; }
                .header { padding: 24px 20px; }
                .content { padding: 20px; }
                .footer { padding: 16px 20px; }
                .header-info { grid-template-columns: 1fr; gap: 12px; }
                .news-header { gap: 6px; }
                .news-content { padding-right: 45px; }
                .news-item { gap: 8px; }
                .new-item { gap: 8px; }
                .news-number { width: 20px; height: 20px; font-size: 12px; }
                .save-buttons {
                    position: static;
                    margin-bottom: 16px;
                    display: flex;
                    gap: 8px;
                    justify-content: center;
                    flex-direction: column;
                    width: 100%;
                }
                .save-btn {
                    width: 100%;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="save-buttons">
                    <button class="save-btn" onclick="saveAsImage()">Save as Image</button>
                    <button class="save-btn" onclick="saveAsMultipleImages()">Save Segments</button>
                </div>
                <div class="header-title">Hot News Analysis</div>
                <div class="header-info">
                    <div class="info-item">
                        <span class="info-label">Report Type</span>
                        <span class="info-value">"""

    # Handle report type display
    if is_daily_summary:
        if mode == "current":
            html += "Current Ranking"
        elif mode == "incremental":
            html += "Incremental"
        else:
            html += "Daily Summary"
    else:
        html += "Realtime Analysis"

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Total News</span>
                        <span class="info-value">"""

    html += f"{total_titles}"

    # Calculate filtered hot news count
    hot_news_count = sum(len(stat["titles"]) for stat in report_data["stats"])

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Hot News</span>
                        <span class="info-value">"""

    html += f"{hot_news_count}"

    html += """</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Generated</span>
                        <span class="info-value">"""

    now = get_beijing_time()
    html += now.strftime("%m-%d %H:%M")

    html += """</span>
                    </div>
                </div>
            </div>
            
            <div class="content">"""

    # Handle failed IDs error info
    if report_data["failed_ids"]:
        html += """
                <div class="error-section">
                    <div class="error-title">⚠️ Failed Platforms</div>
                    <ul class="error-list">"""
        for id_value in report_data["failed_ids"]:
            html += f'<li class="error-item">{html_escape(id_value)}</li>'
        html += """
                    </ul>
                </div>"""

    # Handle main statistics data
    if report_data["stats"]:
        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"], 1):
            count = stat["count"]

            # Determine heat level
            if count >= 10:
                count_class = "hot"
            elif count >= 5:
                count_class = "warm"
            else:
                count_class = ""

            escaped_word = html_escape(stat["word"])

            html += f"""
                <div class="word-group">
                    <div class="word-header">
                        <div class="word-info">
                            <div class="word-name">{escaped_word}</div>
                            <div class="word-count {count_class}">{count} items</div>
                        </div>
                        <div class="word-index">{i}/{total_count}</div>
                    </div>"""

            # Process news titles under each word group, number each news item
            for j, title_data in enumerate(stat["titles"], 1):
                is_new = title_data.get("is_new", False)
                new_class = "new" if is_new else ""

                html += f"""
                    <div class="news-item {new_class}">
                        <div class="news-number">{j}</div>
                        <div class="news-content">
                            <div class="news-header">
                                <span class="source-name">{html_escape(title_data["source_name"])}</span>"""

                # Handle rank display
                ranks = title_data.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_threshold = title_data.get("rank_threshold", 10)

                    # Determine rank level
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= rank_threshold:
                        rank_class = "high"
                    else:
                        rank_class = ""

                    if min_rank == max_rank:
                        rank_text = str(min_rank)
                    else:
                        rank_text = f"{min_rank}-{max_rank}"

                    html += f'<span class="rank-num {rank_class}">{rank_text}</span>'

                # Handle time display
                time_display = title_data.get("time_display", "")
                if time_display:
                    # Simplify time display format, replace tilde
                    simplified_time = (
                        time_display.replace(" ~ ", "~")
                        .replace("[", "")
                        .replace("]", "")
                    )
                    html += (
                        f'<span class="time-info">{html_escape(simplified_time)}</span>'
                    )

                # Handle occurrence count
                count_info = title_data.get("count", 1)
                if count_info > 1:
                    html += f'<span class="count-info">{count_info}x</span>'

                html += """
                            </div>
                            <div class="news-title">"""

                # Handle title and links
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")

                if link_url:
                    escaped_url = html_escape(link_url)
                    html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    html += escaped_title

                html += """
                            </div>
                        </div>
                    </div>"""

            html += """
                </div>"""

    # Handle new news section
    if report_data["new_titles"]:
        html += f"""
                <div class="new-section">
                    <div class="new-section-title">New Hot Topics ({report_data['total_new_count']} total)</div>"""

        for source_data in report_data["new_titles"]:
            escaped_source = html_escape(source_data["source_name"])
            titles_count = len(source_data["titles"])

            html += f"""
                    <div class="new-source-group">
                        <div class="new-source-title">{escaped_source} · {titles_count} items</div>"""

            # Add numbering for new news items too
            for idx, title_data in enumerate(source_data["titles"], 1):
                ranks = title_data.get("ranks", [])

                # Handle rank display for new news
                rank_class = ""
                if ranks:
                    min_rank = min(ranks)
                    if min_rank <= 3:
                        rank_class = "top"
                    elif min_rank <= title_data.get("rank_threshold", 10):
                        rank_class = "high"

                    if len(ranks) == 1:
                        rank_text = str(ranks[0])
                    else:
                        rank_text = f"{min(ranks)}-{max(ranks)}"
                else:
                    rank_text = "?"

                html += f"""
                        <div class="new-item">
                            <div class="new-item-number">{idx}</div>
                            <div class="new-item-rank {rank_class}">{rank_text}</div>
                            <div class="new-item-content">
                                <div class="new-item-title">"""

                # Handle new news links
                escaped_title = html_escape(title_data["title"])
                link_url = title_data.get("mobile_url") or title_data.get("url", "")

                if link_url:
                    escaped_url = html_escape(link_url)
                    html += f'<a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
                else:
                    html += escaped_title

                html += """
                                </div>
                            </div>
                        </div>"""

            html += """
                    </div>"""

        html += """
                </div>"""

    html += """
            </div>

            <div class="footer">
                <div class="footer-content">
                    Generated by <span class="project-name">TrendRadar</span> ·
                    <a href="https://github.com/sansan0/TrendRadar" target="_blank" class="footer-link">
                        GitHub Open Source
                    </a>"""

    if update_info:
        html += f"""
                    <br>
                    <span style="color: #ea580c; font-weight: 500;">
                        New version {update_info['remote_version']} available, current {update_info['current_version']}
                    </span>"""

    html += """
                </div>
            </div>
        </div>
        
        <script>
            async function saveAsImage() {
                const button = event.target;
                const originalText = button.textContent;
                
                try {
                    button.textContent = 'Generating...';
                    button.disabled = true;
                    window.scrollTo(0, 0);

                    // Wait for page to stabilize
                    await new Promise(resolve => setTimeout(resolve, 200));

                    // Hide buttons before screenshot
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';

                    // Wait again to ensure buttons are hidden
                    await new Promise(resolve => setTimeout(resolve, 100));
                    
                    const container = document.querySelector('.container');
                    
                    const canvas = await html2canvas(container, {
                        backgroundColor: '#ffffff',
                        scale: 1.5,
                        useCORS: true,
                        allowTaint: false,
                        imageTimeout: 10000,
                        removeContainer: false,
                        foreignObjectRendering: false,
                        logging: false,
                        width: container.offsetWidth,
                        height: container.offsetHeight,
                        x: 0,
                        y: 0,
                        scrollX: 0,
                        scrollY: 0,
                        windowWidth: window.innerWidth,
                        windowHeight: window.innerHeight
                    });
                    
                    buttons.style.visibility = 'visible';
                    
                    const link = document.createElement('a');
                    const now = new Date();
                    const filename = `TrendRadar_HotNews_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}.png`;

                    link.download = filename;
                    link.href = canvas.toDataURL('image/png', 1.0);

                    // Trigger download
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    button.textContent = 'Saved!';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                    
                } catch (error) {
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    button.textContent = 'Save Failed';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                }
            }
            
            async function saveAsMultipleImages() {
                const button = event.target;
                const originalText = button.textContent;
                const container = document.querySelector('.container');
                const scale = 1.5; 
                const maxHeight = 5000 / scale;
                
                try {
                    button.textContent = 'Analyzing...';
                    button.disabled = true;
                    
                    // Get all possible split elements
                    const newsItems = Array.from(container.querySelectorAll('.news-item'));
                    const wordGroups = Array.from(container.querySelectorAll('.word-group'));
                    const newSection = container.querySelector('.new-section');
                    const errorSection = container.querySelector('.error-section');
                    const header = container.querySelector('.header');
                    const footer = container.querySelector('.footer');

                    // Calculate element positions and heights
                    const containerRect = container.getBoundingClientRect();
                    const elements = [];

                    // Add header as required element
                    elements.push({
                        type: 'header',
                        element: header,
                        top: 0,
                        bottom: header.offsetHeight,
                        height: header.offsetHeight
                    });
                    
                    // Add error section (if exists)
                    if (errorSection) {
                        const rect = errorSection.getBoundingClientRect();
                        elements.push({
                            type: 'error',
                            element: errorSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }
                    
                    // Process news-items by word-group
                    wordGroups.forEach(group => {
                        const groupRect = group.getBoundingClientRect();
                        const groupNewsItems = group.querySelectorAll('.news-item');
                        
                        // Add word-group header section
                        const wordHeader = group.querySelector('.word-header');
                        if (wordHeader) {
                            const headerRect = wordHeader.getBoundingClientRect();
                            elements.push({
                                type: 'word-header',
                                element: wordHeader,
                                parent: group,
                                top: groupRect.top - containerRect.top,
                                bottom: headerRect.bottom - containerRect.top,
                                height: headerRect.height
                            });
                        }
                        
                        // Add each news-item
                        groupNewsItems.forEach(item => {
                            const rect = item.getBoundingClientRect();
                            elements.push({
                                type: 'news-item',
                                element: item,
                                parent: group,
                                top: rect.top - containerRect.top,
                                bottom: rect.bottom - containerRect.top,
                                height: rect.height
                            });
                        });
                    });
                    
                    // Add new news section
                    if (newSection) {
                        const rect = newSection.getBoundingClientRect();
                        elements.push({
                            type: 'new-section',
                            element: newSection,
                            top: rect.top - containerRect.top,
                            bottom: rect.bottom - containerRect.top,
                            height: rect.height
                        });
                    }
                    
                    // Add footer
                    const footerRect = footer.getBoundingClientRect();
                    elements.push({
                        type: 'footer',
                        element: footer,
                        top: footerRect.top - containerRect.top,
                        bottom: footerRect.bottom - containerRect.top,
                        height: footer.offsetHeight
                    });
                    
                    // Calculate split points
                    const segments = [];
                    let currentSegment = { start: 0, end: 0, height: 0, includeHeader: true };
                    let headerHeight = header.offsetHeight;
                    currentSegment.height = headerHeight;
                    
                    for (let i = 1; i < elements.length; i++) {
                        const element = elements[i];
                        const potentialHeight = element.bottom - currentSegment.start;
                        
                        // Check if new segment is needed
                        if (potentialHeight > maxHeight && currentSegment.height > headerHeight) {
                            // Split at end of previous element
                            currentSegment.end = elements[i - 1].bottom;
                            segments.push(currentSegment);
                            
                            // Start new segment
                            currentSegment = {
                                start: currentSegment.end,
                                end: 0,
                                height: element.bottom - currentSegment.end,
                                includeHeader: false
                            };
                        } else {
                            currentSegment.height = potentialHeight;
                            currentSegment.end = element.bottom;
                        }
                    }
                    
                    // Add last segment
                    if (currentSegment.height > 0) {
                        currentSegment.end = container.offsetHeight;
                        segments.push(currentSegment);
                    }
                    
                    button.textContent = `Generating (0/${segments.length})...`;
                    
                    // Hide save buttons
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'hidden';
                    
                    // Generate images for each segment
                    const images = [];
                    for (let i = 0; i < segments.length; i++) {
                        const segment = segments[i];
                        button.textContent = `Generating (${i + 1}/${segments.length})...`;
                        
                        // Create temp container for screenshot
                        const tempContainer = document.createElement('div');
                        tempContainer.style.cssText = `
                            position: absolute;
                            left: -9999px;
                            top: 0;
                            width: ${container.offsetWidth}px;
                            background: white;
                        `;
                        tempContainer.className = 'container';
                        
                        // Clone container content
                        const clonedContainer = container.cloneNode(true);
                        
                        // Remove save buttons from cloned content
                        const clonedButtons = clonedContainer.querySelector('.save-buttons');
                        if (clonedButtons) {
                            clonedButtons.style.display = 'none';
                        }
                        
                        tempContainer.appendChild(clonedContainer);
                        document.body.appendChild(tempContainer);
                        
                        // Wait for DOM update
                        await new Promise(resolve => setTimeout(resolve, 100));
                        
                        // Use html2canvas to capture specific area
                        const canvas = await html2canvas(clonedContainer, {
                            backgroundColor: '#ffffff',
                            scale: scale,
                            useCORS: true,
                            allowTaint: false,
                            imageTimeout: 10000,
                            logging: false,
                            width: container.offsetWidth,
                            height: segment.end - segment.start,
                            x: 0,
                            y: segment.start,
                            windowWidth: window.innerWidth,
                            windowHeight: window.innerHeight
                        });
                        
                        images.push(canvas.toDataURL('image/png', 1.0));
                        
                        // Clean up temp container
                        document.body.removeChild(tempContainer);
                    }
                    
                    // Restore button visibility
                    buttons.style.visibility = 'visible';
                    
                    // Download all images
                    const now = new Date();
                    const baseFilename = `TrendRadar_HotNews_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`;
                    
                    for (let i = 0; i < images.length; i++) {
                        const link = document.createElement('a');
                        link.download = `${baseFilename}_part${i + 1}.png`;
                        link.href = images[i];
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        
                        // Delay to prevent browser blocking multiple downloads
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    
                    button.textContent = `Saved ${segments.length} images!`;
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                    
                } catch (error) {
                    console.error('Save failed:', error);
                    const buttons = document.querySelector('.save-buttons');
                    buttons.style.visibility = 'visible';
                    button.textContent = 'Save failed';
                    setTimeout(() => {
                        button.textContent = originalText;
                        button.disabled = false;
                    }, 2000);
                }
            }
            
            document.addEventListener('DOMContentLoaded', function() {
                window.scrollTo(0, 0);
            });
        </script>
    </body>
    </html>
    """

    return html


def render_feishu_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """Render Feishu content"""
    text_content = ""

    if report_data["stats"]:
        text_content += f"📊 **Hot Keywords Statistics**\n\n"

    total_count = len(report_data["stats"])

    for i, stat in enumerate(report_data["stats"]):
        word = stat["word"]
        count = stat["count"]

        sequence_display = f"<font color='grey'>[{i + 1}/{total_count}]</font>"

        if count >= 10:
            text_content += f"🔥 {sequence_display} **{word}** : <font color='red'>{count}</font> items\n\n"
        elif count >= 5:
            text_content += f"📈 {sequence_display} **{word}** : <font color='orange'>{count}</font> items\n\n"
        else:
            text_content += f"📌 {sequence_display} **{word}** : {count} items\n\n"

        for j, title_data in enumerate(stat["titles"], 1):
            formatted_title = format_title_for_platform(
                "feishu", title_data, show_source=True
            )
            text_content += f"  {j}. {formatted_title}\n"

            if j < len(stat["titles"]):
                text_content += "\n"

        if i < len(report_data["stats"]) - 1:
            text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

    if not text_content:
        if mode == "incremental":
            mode_text = "No new matching hot keywords in incremental mode"
        elif mode == "current":
            mode_text = "No matching hot keywords in current ranking mode"
        else:
            mode_text = "No matching hot keywords"
        text_content = f"📭 {mode_text}\n\n"

    if report_data["new_titles"]:
        if text_content and "No matching" not in text_content:
            text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

        text_content += (
            f"🆕 **New Hot News** ({report_data['total_new_count']} total)\n\n"
        )

        for source_data in report_data["new_titles"]:
            text_content += (
                f"**{source_data['source_name']}** ({len(source_data['titles'])} items):\n"
            )

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "feishu", title_data_copy, show_source=False
                )
                text_content += f"  {j}. {formatted_title}\n"

            text_content += "\n"

    if report_data["failed_ids"]:
        if text_content and "No matching" not in text_content:
            text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

        text_content += "⚠️ **Failed Platforms:**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  • <font color='red'>{id_value}</font>\n"

    now = get_beijing_time()
    text_content += (
        f"\n\n<font color='grey'>Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"
    )

    if update_info:
        text_content += f"\n<font color='grey'>TrendRadar New version available {update_info['remote_version']}, current {update_info['current_version']}</font>"

    return text_content


def render_dingtalk_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """Render DingTalk content"""
    text_content = ""

    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    now = get_beijing_time()

    text_content += f"**Total news:** {total_titles}\n\n"
    text_content += f"**Time:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    text_content += f"**Type:** Hot News Report\n\n"

    text_content += "---\n\n"

    if report_data["stats"]:
        text_content += f"📊 **Hot Keywords Statistics**\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"[{i + 1}/{total_count}]"

            if count >= 10:
                text_content += f"🔥 {sequence_display} **{word}** : **{count}** items\n\n"
            elif count >= 5:
                text_content += f"📈 {sequence_display} **{word}** : **{count}** items\n\n"
            else:
                text_content += f"📌 {sequence_display} **{word}** : {count} items\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data, show_source=True
                )
                text_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    text_content += "\n"

            if i < len(report_data["stats"]) - 1:
                text_content += f"\n---\n\n"

    if not report_data["stats"]:
        if mode == "incremental":
            mode_text = "No new matching hot keywords in incremental mode"
        elif mode == "current":
            mode_text = "No matching hot keywords in current ranking mode"
        else:
            mode_text = "No matching hot keywords"
        text_content += f"📭 {mode_text}\n\n"

    if report_data["new_titles"]:
        if text_content and "No matching" not in text_content:
            text_content += f"\n---\n\n"

        text_content += (
            f"🆕 **New Hot News** ({report_data['total_new_count']} total)\n\n"
        )

        for source_data in report_data["new_titles"]:
            text_content += f"**{source_data['source_name']}** ({len(source_data['titles'])} items):\n\n"

            for j, title_data in enumerate(source_data["titles"], 1):
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False
                formatted_title = format_title_for_platform(
                    "dingtalk", title_data_copy, show_source=False
                )
                text_content += f"  {j}. {formatted_title}\n"

            text_content += "\n"

    if report_data["failed_ids"]:
        if text_content and "No matching" not in text_content:
            text_content += f"\n---\n\n"

        text_content += "⚠️ **Failed Platforms:**\n\n"
        for i, id_value in enumerate(report_data["failed_ids"], 1):
            text_content += f"  • **{id_value}**\n"

    text_content += f"\n\n> Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}"

    if update_info:
        text_content += f"\n> TrendRadar New version available **{update_info['remote_version']}**, current **{update_info['current_version']}**"

    return text_content


def _get_batch_header(format_type: str, batch_num: int, total_batches: int) -> str:
    """Generate batch header based on format_type"""
    if format_type == "telegram":
        return f"<b>[Part {batch_num}/{total_batches}]</b>\n\n"
    elif format_type == "slack":
        return f"*[Part {batch_num}/{total_batches}]*\n\n"
    elif format_type in ("wework_text", "bark"):
        # WeCom text mode and Bark use plain text format
        return f"[Part {batch_num}/{total_batches}]\n\n"
    else:
        # Feishu, DingTalk, ntfy, WeCom markdown mode
        return f"**[Part {batch_num}/{total_batches}]**\n\n"


def _get_max_batch_header_size(format_type: str) -> int:
    """Estimate max batch header size in bytes (assuming max 99 batches)

    Used to reserve space during batching to avoid truncating content.
    """
    # Generate worst-case header (99/99 batches)
    max_header = _get_batch_header(format_type, 99, 99)
    return len(max_header.encode("utf-8"))


def _truncate_to_bytes(text: str, max_bytes: int) -> str:
    """Safely truncate string to specified bytes, avoiding multi-byte character breaks"""
    text_bytes = text.encode("utf-8")
    if len(text_bytes) <= max_bytes:
        return text

    # Truncate to specified bytes
    truncated = text_bytes[:max_bytes]

    # Handle potentially incomplete UTF-8 characters
    for i in range(min(4, len(truncated))):
        try:
            return truncated[: len(truncated) - i].decode("utf-8")
        except UnicodeDecodeError:
            continue

    # Edge case: return empty string
    return ""


def add_batch_headers(
    batches: List[str], format_type: str, max_bytes: int
) -> List[str]:
    """Add headers to batches, dynamically calculate to ensure total size doesn't exceed limit

    Args:
        batches: Original batch list
        format_type: Push type (bark, telegram, feishu, etc.)
        max_bytes: Max byte limit for this push type

    Returns:
        Batch list with headers added
    """
    if len(batches) <= 1:
        return batches

    total = len(batches)
    result = []

    for i, content in enumerate(batches, 1):
        # Generate batch header
        header = _get_batch_header(format_type, i, total)
        header_size = len(header.encode("utf-8"))

        # Dynamically calculate max allowed content size
        max_content_size = max_bytes - header_size
        content_size = len(content.encode("utf-8"))

        # If exceeded, truncate to safe size
        if content_size > max_content_size:
            print(
                f"Warning: {format_type} part {i}/{total} content({content_size} bytes) + header({header_size} bytes) exceeds limit({max_bytes} bytes), truncating to {max_content_size} bytes"
            )
            content = _truncate_to_bytes(content, max_content_size)

        result.append(header + content)

    return result


def split_content_into_batches(
    report_data: Dict,
    format_type: str,
    update_info: Optional[Dict] = None,
    max_bytes: int = None,
    mode: str = "daily",
) -> List[str]:
    """Split message content into batches, ensuring keyword title + at least first news item stays together"""
    if max_bytes is None:
        if format_type == "dingtalk":
            max_bytes = CONFIG.get("DINGTALK_BATCH_SIZE", 20000)
        elif format_type == "feishu":
            max_bytes = CONFIG.get("FEISHU_BATCH_SIZE", 29000)
        elif format_type == "ntfy":
            max_bytes = 3800
        else:
            max_bytes = CONFIG.get("MESSAGE_BATCH_SIZE", 4000)

    batches = []

    total_titles = sum(
        len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
    )
    now = get_beijing_time()

    base_header = ""
    if format_type in ("wework", "bark"):
        base_header = f"**Total news:** {total_titles}\n\n\n\n"
    elif format_type == "telegram":
        base_header = f"Total news: {total_titles}\n\n"
    elif format_type == "ntfy":
        base_header = f"**Total news:** {total_titles}\n\n"
    elif format_type == "feishu":
        base_header = ""
    elif format_type == "dingtalk":
        base_header = f"**Total news:** {total_titles}\n\n"
        base_header += f"**Time:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        base_header += f"**Type:** Hot News Report\n\n"
        base_header += "---\n\n"
    elif format_type == "slack":
        base_header = f"*Total news:* {total_titles}\n\n"

    base_footer = ""
    if format_type in ("wework", "bark"):
        base_footer = f"\n\n\n> Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar New version available **{update_info['remote_version']}**, current **{update_info['current_version']}**"
    elif format_type == "telegram":
        base_footer = f"\n\nUpdated:{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\nTrendRadar New version available {update_info['remote_version']}, current {update_info['current_version']}"
    elif format_type == "ntfy":
        base_footer = f"\n\n> Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar New version available **{update_info['remote_version']}**, current **{update_info['current_version']}**"
    elif format_type == "feishu":
        base_footer = f"\n\n<font color='grey'>Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"
        if update_info:
            base_footer += f"\n<font color='grey'>TrendRadar New version available {update_info['remote_version']}, current {update_info['current_version']}</font>"
    elif format_type == "dingtalk":
        base_footer = f"\n\n> Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}"
        if update_info:
            base_footer += f"\n> TrendRadar New version available **{update_info['remote_version']}**, current **{update_info['current_version']}**"
    elif format_type == "slack":
        base_footer = f"\n\n_Updated:{now.strftime('%Y-%m-%d %H:%M:%S')}_"
        if update_info:
            base_footer += f"\n_TrendRadar New version available *{update_info['remote_version']}*, current *{update_info['current_version']}_"

    stats_header = ""
    if report_data["stats"]:
        if format_type in ("wework", "bark"):
            stats_header = f"📊 **Hot Keywords Statistics**\n\n"
        elif format_type == "telegram":
            stats_header = f"📊 Hot Keywords Statistics\n\n"
        elif format_type == "ntfy":
            stats_header = f"📊 **Hot Keywords Statistics**\n\n"
        elif format_type == "feishu":
            stats_header = f"📊 **Hot Keywords Statistics**\n\n"
        elif format_type == "dingtalk":
            stats_header = f"📊 **Hot Keywords Statistics**\n\n"
        elif format_type == "slack":
            stats_header = f"📊 *Hot Keywords Statistics*\n\n"

    current_batch = base_header
    current_batch_has_content = False

    if (
        not report_data["stats"]
        and not report_data["new_titles"]
        and not report_data["failed_ids"]
    ):
        if mode == "incremental":
            mode_text = "No new matching hot keywords in incremental mode"
        elif mode == "current":
            mode_text = "No matching hot keywords in current ranking mode"
        else:
            mode_text = "No matching hot keywords"
        simple_content = f"📭 {mode_text}\n\n"
        final_content = base_header + simple_content + base_footer
        batches.append(final_content)
        return batches

    # Process Hot Keywords Statistics
    if report_data["stats"]:
        total_count = len(report_data["stats"])

        # Add statistics header
        test_content = current_batch + stats_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            < max_bytes
        ):
            current_batch = test_content
            current_batch_has_content = True
        else:
            if current_batch_has_content:
                batches.append(current_batch + base_footer)
            current_batch = base_header + stats_header
            current_batch_has_content = True

        # Process keywords one by one (ensure keyword title + first news stay atomic)
        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]
            sequence_display = f"[{i + 1}/{total_count}]"

            # Build keyword title
            word_header = ""
            if format_type in ("wework", "bark"):
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** items\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** items\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} items\n\n"
            elif format_type == "telegram":
                if count >= 10:
                    word_header = f"🔥 {sequence_display} {word} : {count} items\n\n"
                elif count >= 5:
                    word_header = f"📈 {sequence_display} {word} : {count} items\n\n"
                else:
                    word_header = f"📌 {sequence_display} {word} : {count} items\n\n"
            elif format_type == "ntfy":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** items\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** items\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} items\n\n"
            elif format_type == "feishu":
                if count >= 10:
                    word_header = f"🔥 <font color='grey'>{sequence_display}</font> **{word}** : <font color='red'>{count}</font> items\n\n"
                elif count >= 5:
                    word_header = f"📈 <font color='grey'>{sequence_display}</font> **{word}** : <font color='orange'>{count}</font> items\n\n"
                else:
                    word_header = f"📌 <font color='grey'>{sequence_display}</font> **{word}** : {count} items\n\n"
            elif format_type == "dingtalk":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} **{word}** : **{count}** items\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} **{word}** : **{count}** items\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} **{word}** : {count} items\n\n"
            elif format_type == "slack":
                if count >= 10:
                    word_header = (
                        f"🔥 {sequence_display} *{word}* : *{count}* items\n\n"
                    )
                elif count >= 5:
                    word_header = (
                        f"📈 {sequence_display} *{word}* : *{count}* items\n\n"
                    )
                else:
                    word_header = f"📌 {sequence_display} *{word}* : {count} items\n\n"

            # Build first news item
            first_news_line = ""
            if stat["titles"]:
                first_title_data = stat["titles"][0]
                if format_type in ("wework", "bark"):
                    formatted_title = format_title_for_platform(
                        "wework", first_title_data, show_source=True
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", first_title_data, show_source=True
                    )
                elif format_type == "ntfy":
                    formatted_title = format_title_for_platform(
                        "ntfy", first_title_data, show_source=True
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", first_title_data, show_source=True
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", first_title_data, show_source=True
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", first_title_data, show_source=True
                    )
                else:
                    formatted_title = f"{first_title_data['title']}"

                first_news_line = f"  1. {formatted_title}\n"
                if len(stat["titles"]) > 1:
                    first_news_line += "\n"

            # Atomicity check: keyword title + first news must be processed together
            word_with_first_news = word_header + first_news_line
            test_content = current_batch + word_with_first_news

            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                # Current batch can't fit, start new batch
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + stats_header + word_with_first_news
                current_batch_has_content = True
                start_index = 1
            else:
                current_batch = test_content
                current_batch_has_content = True
                start_index = 1

            # Process remaining news items
            for j in range(start_index, len(stat["titles"])):
                title_data = stat["titles"][j]
                if format_type in ("wework", "bark"):
                    formatted_title = format_title_for_platform(
                        "wework", title_data, show_source=True
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data, show_source=True
                    )
                elif format_type == "ntfy":
                    formatted_title = format_title_for_platform(
                        "ntfy", title_data, show_source=True
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", title_data, show_source=True
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", title_data, show_source=True
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", title_data, show_source=True
                    )
                else:
                    formatted_title = f"{title_data['title']}"

                news_line = f"  {j + 1}. {formatted_title}\n"
                if j < len(stat["titles"]) - 1:
                    news_line += "\n"

                test_content = current_batch + news_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + stats_header + word_header + news_line
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

            # Separator between keywords
            if i < len(report_data["stats"]) - 1:
                separator = ""
                if format_type in ("wework", "bark"):
                    separator = f"\n\n\n\n"
                elif format_type == "telegram":
                    separator = f"\n\n"
                elif format_type == "ntfy":
                    separator = f"\n\n"
                elif format_type == "feishu":
                    separator = f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"
                elif format_type == "dingtalk":
                    separator = f"\n---\n\n"
                elif format_type == "slack":
                    separator = f"\n\n"

                test_content = current_batch + separator
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    < max_bytes
                ):
                    current_batch = test_content

    # Process new news (also ensure source title + first news stay atomic)
    if report_data["new_titles"]:
        new_header = ""
        if format_type in ("wework", "bark"):
            new_header = f"\n\n\n\n🆕 **New Hot News** ({report_data['total_new_count']} total)\n\n"
        elif format_type == "telegram":
            new_header = (
                f"\n\n🆕 New Hot News ({report_data['total_new_count']} total)\n\n"
            )
        elif format_type == "ntfy":
            new_header = f"\n\n🆕 **New Hot News** ({report_data['total_new_count']} total)\n\n"
        elif format_type == "feishu":
            new_header = f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n🆕 **New Hot News** ({report_data['total_new_count']} total)\n\n"
        elif format_type == "dingtalk":
            new_header = f"\n---\n\n🆕 **New Hot News** ({report_data['total_new_count']} total)\n\n"
        elif format_type == "slack":
            new_header = f"\n\n🆕 *New Hot News* ({report_data['total_new_count']} total)\n\n"

        test_content = current_batch + new_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            >= max_bytes
        ):
            if current_batch_has_content:
                batches.append(current_batch + base_footer)
            current_batch = base_header + new_header
            current_batch_has_content = True
        else:
            current_batch = test_content
            current_batch_has_content = True

        # Process new news sources one by one
        for source_data in report_data["new_titles"]:
            source_header = ""
            if format_type in ("wework", "bark"):
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} items):\n\n"
            elif format_type == "telegram":
                source_header = f"{source_data['source_name']} ({len(source_data['titles'])} items):\n\n"
            elif format_type == "ntfy":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} items):\n\n"
            elif format_type == "feishu":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} items):\n\n"
            elif format_type == "dingtalk":
                source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} items):\n\n"
            elif format_type == "slack":
                source_header = f"*{source_data['source_name']}* ({len(source_data['titles'])} items):\n\n"

            # Build first new news item
            first_news_line = ""
            if source_data["titles"]:
                first_title_data = source_data["titles"][0]
                title_data_copy = first_title_data.copy()
                title_data_copy["is_new"] = False

                if format_type in ("wework", "bark"):
                    formatted_title = format_title_for_platform(
                        "wework", title_data_copy, show_source=False
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data_copy, show_source=False
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", title_data_copy, show_source=False
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", title_data_copy, show_source=False
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", title_data_copy, show_source=False
                    )
                else:
                    formatted_title = f"{title_data_copy['title']}"

                first_news_line = f"  1. {formatted_title}\n"

            # Atomicity check: source title + first news
            source_with_first_news = source_header + first_news_line
            test_content = current_batch + source_with_first_news

            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + new_header + source_with_first_news
                current_batch_has_content = True
                start_index = 1
            else:
                current_batch = test_content
                current_batch_has_content = True
                start_index = 1

            # Process remaining new news
            for j in range(start_index, len(source_data["titles"])):
                title_data = source_data["titles"][j]
                title_data_copy = title_data.copy()
                title_data_copy["is_new"] = False

                if format_type == "wework":
                    formatted_title = format_title_for_platform(
                        "wework", title_data_copy, show_source=False
                    )
                elif format_type == "telegram":
                    formatted_title = format_title_for_platform(
                        "telegram", title_data_copy, show_source=False
                    )
                elif format_type == "feishu":
                    formatted_title = format_title_for_platform(
                        "feishu", title_data_copy, show_source=False
                    )
                elif format_type == "dingtalk":
                    formatted_title = format_title_for_platform(
                        "dingtalk", title_data_copy, show_source=False
                    )
                elif format_type == "slack":
                    formatted_title = format_title_for_platform(
                        "slack", title_data_copy, show_source=False
                    )
                else:
                    formatted_title = f"{title_data_copy['title']}"

                news_line = f"  {j + 1}. {formatted_title}\n"

                test_content = current_batch + news_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + new_header + source_header + news_line
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

            current_batch += "\n"

    if report_data["failed_ids"]:
        failed_header = ""
        if format_type == "wework":
            failed_header = f"\n\n\n\n⚠️ **Failed Platforms:**\n\n"
        elif format_type == "telegram":
            failed_header = f"\n\n⚠️ Failed Platforms:\n\n"
        elif format_type == "ntfy":
            failed_header = f"\n\n⚠️ **Failed Platforms:**\n\n"
        elif format_type == "feishu":
            failed_header = f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n⚠️ **Failed Platforms:**\n\n"
        elif format_type == "dingtalk":
            failed_header = f"\n---\n\n⚠️ **Failed Platforms:**\n\n"

        test_content = current_batch + failed_header
        if (
            len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
            >= max_bytes
        ):
            if current_batch_has_content:
                batches.append(current_batch + base_footer)
            current_batch = base_header + failed_header
            current_batch_has_content = True
        else:
            current_batch = test_content
            current_batch_has_content = True

        for i, id_value in enumerate(report_data["failed_ids"], 1):
            if format_type == "feishu":
                failed_line = f"  • <font color='red'>{id_value}</font>\n"
            elif format_type == "dingtalk":
                failed_line = f"  • **{id_value}**\n"
            else:
                failed_line = f"  • {id_value}\n"

            test_content = current_batch + failed_line
            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + failed_header + failed_line
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

    # Complete last batch
    if current_batch_has_content:
        batches.append(current_batch + base_footer)

    return batches


def send_to_notifications(
    stats: List[Dict],
    failed_ids: Optional[List] = None,
    report_type: str = "Daily Summary",
    new_titles: Optional[Dict] = None,
    id_to_name: Optional[Dict] = None,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
    html_file_path: Optional[str] = None,
) -> Dict[str, bool]:
    """Send data to multiple notification platforms"""
    results = {}

    if CONFIG["PUSH_WINDOW"]["ENABLED"]:
        push_manager = PushRecordManager()
        time_range_start = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["START"]
        time_range_end = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["END"]

        if not push_manager.is_in_time_range(time_range_start, time_range_end):
            now = get_beijing_time()
            print(
                f"Push window control: current time {now.strftime('%H:%M')} not in push window {time_range_start}-{time_range_end}, skipping"
            )
            return results

        if CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"]:
            if push_manager.has_pushed_today():
                print(f"Push window control: already pushed today, skipping")
                return results
            else:
                print(f"Push window control: first push today")

    report_data = prepare_report_data(stats, failed_ids, new_titles, id_to_name, mode)

    feishu_url = CONFIG["FEISHU_WEBHOOK_URL"]
    dingtalk_url = CONFIG["DINGTALK_WEBHOOK_URL"]
    wework_url = CONFIG["WEWORK_WEBHOOK_URL"]
    telegram_token = CONFIG["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = CONFIG["TELEGRAM_CHAT_ID"]
    email_from = CONFIG["EMAIL_FROM"]
    email_password = CONFIG["EMAIL_PASSWORD"]
    email_to = CONFIG["EMAIL_TO"]
    email_smtp_server = CONFIG.get("EMAIL_SMTP_SERVER", "")
    email_smtp_port = CONFIG.get("EMAIL_SMTP_PORT", "")
    resend_api_key = CONFIG.get("RESEND_API_KEY", "")
    resend_from_email = CONFIG.get("RESEND_FROM_EMAIL", "")
    resend_to_email = CONFIG.get("RESEND_TO_EMAIL", "")
    ntfy_server_url = CONFIG["NTFY_SERVER_URL"]
    ntfy_topic = CONFIG["NTFY_TOPIC"]
    ntfy_token = CONFIG.get("NTFY_TOKEN", "")
    bark_url = CONFIG["BARK_URL"]
    slack_webhook_url = CONFIG["SLACK_WEBHOOK_URL"]

    update_info_to_send = update_info if CONFIG["SHOW_VERSION_UPDATE"] else None

    # Send to Feishu
    if feishu_url:
        results["feishu"] = send_to_feishu(
            feishu_url, report_data, report_type, update_info_to_send, proxy_url, mode
        )

    # Send to DingTalk
    if dingtalk_url:
        results["dingtalk"] = send_to_dingtalk(
            dingtalk_url, report_data, report_type, update_info_to_send, proxy_url, mode
        )

    # Send to WeCom
    if wework_url:
        results["wework"] = send_to_wework(
            wework_url, report_data, report_type, update_info_to_send, proxy_url, mode
        )

    # Send to Telegram
    if telegram_token and telegram_chat_id:
        results["telegram"] = send_to_telegram(
            telegram_token,
            telegram_chat_id,
            report_data,
            report_type,
            update_info_to_send,
            proxy_url,
            mode,
        )

    # Send to ntfy
    if ntfy_server_url and ntfy_topic:
        results["ntfy"] = send_to_ntfy(
            ntfy_server_url,
            ntfy_topic,
            ntfy_token,
            report_data,
            report_type,
            update_info_to_send,
            proxy_url,
            mode,
        )

    # Send to Bark
    if bark_url:
        results["bark"] = send_to_bark(
            bark_url,
            report_data,
            report_type,
            update_info_to_send,
            proxy_url,
            mode,
        )

    # Send to Slack
    if slack_webhook_url:
        results["slack"] = send_to_slack(
            slack_webhook_url,
            report_data,
            report_type,
            update_info_to_send,
            proxy_url,
            mode,
        )

    # Send email
    if email_from and email_password and email_to:
        results["email"] = send_to_email(
            email_from,
            email_password,
            email_to,
            report_type,
            html_file_path,
            email_smtp_server,
            email_smtp_port,
        )

    # Send via Resend
    if resend_api_key and resend_from_email and resend_to_email:
        results["resend"] = send_to_resend(
            resend_api_key,
            resend_from_email,
            resend_to_email,
            report_type,
            html_file_path,
        )

    if not results:
        print("No notification channels configured, skipping notification")

    # If any notification was successfully sent and once-per-day is enabled, record the push
    if (
        CONFIG["PUSH_WINDOW"]["ENABLED"]
        and CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"]
        and any(results.values())
    ):
        push_manager = PushRecordManager()
        push_manager.record_push(report_type)

    return results


def send_to_feishu(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to Feishu (supports batch sending)"""
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Get batch content, use Feishu-specific batch size
    feishu_batch_size = CONFIG.get("FEISHU_BATCH_SIZE", 29000)
    # Reserve space for batch header to avoid exceeding limit after adding header
    header_reserve = _get_max_batch_header_size("feishu")
    batches = split_content_into_batches(
        report_data,
        "feishu",
        update_info,
        max_bytes=feishu_batch_size - header_reserve,
        mode=mode,
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, "feishu", feishu_batch_size)

    print(f"Feishu message split into {len(batches)} batches [{report_type}]")

    # Send batch by batch
    for i, batch_content in enumerate(batches, 1):
        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"Sending Feishu batch {i}/{len(batches)}, size: {batch_size} bytes [{report_type}]"
        )

        total_titles = sum(
            len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
        )
        now = get_beijing_time()

        payload = {
            "msg_type": "text",
            "content": {
                "total_titles": total_titles,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "report_type": report_type,
                "text": batch_content,
            },
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                # Check Feishu response status
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    print(f"Feishu batch {i}/{len(batches)} sent successfully [{report_type}]")
                    # Interval between batches
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    error_msg = result.get("msg") or result.get("StatusMessage", "Unknown error")
                    print(
                        f"Feishu batch {i}/{len(batches)} failed [{report_type}], error: {error_msg}"
                    )
                    return False
            else:
                print(
                    f"Feishu batch {i}/{len(batches)} failed [{report_type}]，status code:{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"Feishu batch {i}/{len(batches)} error [{report_type}]：{e}")
            return False

    print(f"Feishu all {len(batches)} batches completed [{report_type}]")
    return True


def send_to_dingtalk(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to DingTalk (supports batch sending)"""
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Get batch content, use DingTalk-specific batch size
    dingtalk_batch_size = CONFIG.get("DINGTALK_BATCH_SIZE", 20000)
    # Reserve space for batch header to avoid exceeding limit after adding header
    header_reserve = _get_max_batch_header_size("dingtalk")
    batches = split_content_into_batches(
        report_data,
        "dingtalk",
        update_info,
        max_bytes=dingtalk_batch_size - header_reserve,
        mode=mode,
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, "dingtalk", dingtalk_batch_size)

    print(f"DingTalk message split into {len(batches)} batches [{report_type}]")

    # Send batch by batch
    for i, batch_content in enumerate(batches, 1):
        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"SendingDingTalk batch {i}/{len(batches)} , size:{batch_size} bytes [{report_type}]"
        )

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"TrendRadar Hot News Report - {report_type}",
                "text": batch_content,
            },
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"DingTalk batch {i}/{len(batches)} sent successfully [{report_type}]")
                    # Interval between batches
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    print(
                        f"DingTalk batch {i}/{len(batches)} failed [{report_type}]，error:{result.get('errmsg')}"
                    )
                    return False
            else:
                print(
                    f"DingTalk batch {i}/{len(batches)} failed [{report_type}]，status code:{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"DingTalk batch {i}/{len(batches)} error [{report_type}]：{e}")
            return False

    print(f"DingTalk all {len(batches)} batches completed [{report_type}]")
    return True


def strip_markdown(text: str) -> str:
    """Remove markdown syntax from text, for personal WeChat push"""

    # Remove bold **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # Remove italic *text* or _text_
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # Remove strikethrough ~~text~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)

    # Convert link [text](url) -> text url (keep URL)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 \2', text)
    # If URL not needed, use this line instead (keep title text only):
    # text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Remove image ![alt](url) -> alt
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)

    # Remove inline code `code`
    text = re.sub(r'`(.+?)`', r'\1', text)

    # Remove quote symbol >
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # Remove heading symbols # ## ### etc
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

    # Remove horizontal divider --- or ***
    text = re.sub(r'^[\-\*]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove HTML tags <font color='xxx'>text</font> -> text
    text = re.sub(r'<font[^>]*>(.+?)</font>', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)

    # Clean up extra blank lines (keep max two consecutive blank lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def send_to_wework(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to WeCom (supports batch sending, supports markdown and text formats)"""
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Get message type config (markdown or text)
    msg_type = CONFIG.get("WEWORK_MSG_TYPE", "markdown").lower()
    is_text_mode = msg_type == "text"

    if is_text_mode:
        print(f"WeCom using text format (personal WeChat mode) [{report_type}]")
    else:
        print(f"WeCom using markdown format (group bot mode) [{report_type}]")

    # text mode uses wework_text, markdown mode uses wework
    header_format_type = "wework_text" if is_text_mode else "wework"

    # Get batch content, reserve space for batch header
    wework_batch_size = CONFIG.get("MESSAGE_BATCH_SIZE", 4000)
    header_reserve = _get_max_batch_header_size(header_format_type)
    batches = split_content_into_batches(
        report_data, "wework", update_info, max_bytes=wework_batch_size - header_reserve, mode=mode
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, header_format_type, wework_batch_size)

    print(f"WeCom message split into {len(batches)} batches [{report_type}]")

    # Send batch by batch
    for i, batch_content in enumerate(batches, 1):
        # Build payload based on message type
        if is_text_mode:
            # text format: remove markdown syntax
            plain_content = strip_markdown(batch_content)
            payload = {"msgtype": "text", "text": {"content": plain_content}}
            batch_size = len(plain_content.encode("utf-8"))
        else:
            # markdown format: keep as is
            payload = {"msgtype": "markdown", "markdown": {"content": batch_content}}
            batch_size = len(batch_content.encode("utf-8"))

        print(
            f"SendingWeCom batch {i}/{len(batches)} , size:{batch_size} bytes [{report_type}]"
        )

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"WeCom batch {i}/{len(batches)} sent successfully [{report_type}]")
                    # Interval between batches
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    print(
                        f"WeCom batch {i}/{len(batches)} failed [{report_type}]，error:{result.get('errmsg')}"
                    )
                    return False
            else:
                print(
                    f"WeCom batch {i}/{len(batches)} failed [{report_type}]，status code:{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"WeCom batch {i}/{len(batches)} error [{report_type}]：{e}")
            return False

    print(f"WeCom all {len(batches)} batches completed [{report_type}]")
    return True


def send_to_telegram(
    bot_token: str,
    chat_id: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to Telegram (supports batch sending)"""
    headers = {"Content-Type": "application/json"}
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Get batch content, reserve space for batch header
    telegram_batch_size = CONFIG.get("MESSAGE_BATCH_SIZE", 4000)
    header_reserve = _get_max_batch_header_size("telegram")
    batches = split_content_into_batches(
        report_data, "telegram", update_info, max_bytes=telegram_batch_size - header_reserve, mode=mode
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, "telegram", telegram_batch_size)

    print(f"Telegram message split into {len(batches)} batches [{report_type}]")

    # Send batch by batch
    for i, batch_content in enumerate(batches, 1):
        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"SendingTelegram batch {i}/{len(batches)} , size:{batch_size} bytes [{report_type}]"
        )

        payload = {
            "chat_id": chat_id,
            "text": batch_content,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(
                url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"Telegram batch {i}/{len(batches)} sent successfully [{report_type}]")
                    # Interval between batches
                    if i < len(batches):
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    print(
                        f"Telegram batch {i}/{len(batches)} failed [{report_type}]，error:{result.get('description')}"
                    )
                    return False
            else:
                print(
                    f"Telegram batch {i}/{len(batches)} failed [{report_type}]，status code:{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"Telegram batch {i}/{len(batches)} error [{report_type}]：{e}")
            return False

    print(f"Telegramall {len(batches)} batches completed [{report_type}]")
    return True


def send_to_email(
    from_email: str,
    password: str,
    to_email: str,
    report_type: str,
    html_file_path: str,
    custom_smtp_server: Optional[str] = None,
    custom_smtp_port: Optional[int] = None,
) -> bool:
    """Send email notification"""
    try:
        if not html_file_path or not Path(html_file_path).exists():
            print(f"Error: HTML file does not exist or not provided: {html_file_path}")
            return False

        print(f"Using HTML file: {html_file_path}")
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        domain = from_email.split("@")[-1].lower()

        if custom_smtp_server and custom_smtp_port:
            # Use custom SMTP config
            smtp_server = custom_smtp_server
            smtp_port = int(custom_smtp_port)
            # Determine encryption based on port: 465=SSL, 587=TLS
            if smtp_port == 465:
                use_tls = False  # SSL mode (SMTP_SSL)
            elif smtp_port == 587:
                use_tls = True   # TLS mode (STARTTLS)
            else:
                # Other ports default to TLS (more secure, widely supported)
                use_tls = True
        elif domain in SMTP_CONFIGS:
            # Use preset config
            config = SMTP_CONFIGS[domain]
            smtp_server = config["server"]
            smtp_port = config["port"]
            use_tls = config["encryption"] == "TLS"
        else:
            print(f"Unrecognized email provider: {domain}, using generic SMTP config")
            smtp_server = f"smtp.{domain}"
            smtp_port = 587
            use_tls = True

        msg = MIMEMultipart("alternative")

        # Set From header according to RFC standard
        sender_name = "TrendRadar"
        msg["From"] = formataddr((sender_name, from_email))

        # Set recipient
        recipients = [addr.strip() for addr in to_email.split(",")]
        if len(recipients) == 1:
            msg["To"] = recipients[0]
        else:
            msg["To"] = ", ".join(recipients)

        # Set email subject
        now = get_beijing_time()
        subject = f"TrendRadar Hot News Report - {report_type} - {now.strftime('%m-%d %H:%M')}"
        msg["Subject"] = Header(subject, "utf-8")

        # Set other standard headers
        msg["MIME-Version"] = "1.0"
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()

        # Add plain text part (as fallback)
        text_content = f"""
TrendRadar Hot News Report
========================
Report Type: {report_type}
Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}

Please use an HTML-supported email client to view the full report.
        """
        text_part = MIMEText(text_content, "plain", "utf-8")
        msg.attach(text_part)

        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        print(f"Sending email to {to_email}...")
        print(f"SMTP server: {smtp_server}:{smtp_port}")
        print(f"Sender: {from_email}")

        try:
            if use_tls:
                # TLS mode
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(0)  # Set to 1 for detailed debug info
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                # SSL mode
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(0)
                server.ehlo()

            # Login
            server.login(from_email, password)

            # Send email
            server.send_message(msg)
            server.quit()

            print(f"Email sent successfully [{report_type}] -> {to_email}")
            return True

        except smtplib.SMTPServerDisconnected:
            print(f"Email sending failed: server unexpectedly disconnected, check network or try again later")
            return False

    except smtplib.SMTPAuthenticationError as e:
        print(f"Email sending failed: authentication error, check email and password/auth code")
        print(f"Error details: {str(e)}")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        print(f"Email sending failed: recipient address refused {e}")
        return False
    except smtplib.SMTPSenderRefused as e:
        print(f"Email sending failed: sender address refused {e}")
        return False
    except smtplib.SMTPDataError as e:
        print(f"Email sending failed: email data error {e}")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"Email sending failed: unable to connect to SMTP server {smtp_server}:{smtp_port}")
        print(f"Error details: {str(e)}")
        return False
    except Exception as e:
        print(f"Email sending failed [{report_type}]: {e}")
        import traceback

        traceback.print_exc()
        return False


def send_to_resend(
    api_key: str,
    from_email: str,
    to_email: str,
    report_type: str,
    html_file_path: str,
) -> bool:
    """Send email notification via Resend API"""
    if not RESEND_AVAILABLE:
        print("Error: resend package not installed. Run: pip install resend")
        return False

    try:
        if not html_file_path or not Path(html_file_path).exists():
            print(f"Error: HTML file does not exist: {html_file_path}")
            return False

        print(f"Using HTML file: {html_file_path}")
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Set API key
        resend.api_key = api_key

        # Parse recipients (comma-separated)
        recipients = [addr.strip() for addr in to_email.split(",")]

        # Prepare email subject
        beijing_tz = pytz.timezone("Asia/Shanghai")
        now = datetime.now(beijing_tz)
        subject = f"TrendRadar {report_type} - {now.strftime('%Y-%m-%d %H:%M')}"

        print(f"Sending email via Resend to {to_email}...")
        print(f"From: {from_email}")

        # Send email via Resend API
        params = {
            "from": f"TrendRadar <{from_email}>",
            "to": recipients,
            "subject": subject,
            "html": html_content,
        }

        result = resend.Emails.send(params)

        if result and result.get("id"):
            print(f"Resend email sent successfully [{report_type}] -> {to_email}: {result['id']}")
            return True
        else:
            print(f"Resend API returned invalid response: {result}")
            return False

    except Exception as e:
        print(f"Resend email failed [{report_type}]: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_to_ntfy(
    server_url: str,
    topic: str,
    token: Optional[str],
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to ntfy (supports batch sending, strictly adheres to 4KB limit)"""
    # Avoid HTTP header encoding issues
    report_type_en_map = {
        "Daily Summary": "Daily Summary",
        "Current Ranking": "Current Ranking",
        "Incremental Update": "Incremental Update",
        "Realtime Incremental": "Realtime Incremental",
        "Realtime Current Ranking": "Realtime Current Ranking",  
    }
    report_type_en = report_type_en_map.get(report_type, "News Report") 

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Markdown": "yes",
        "Title": report_type_en,
        "Priority": "default",
        "Tags": "news",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Build complete URL, ensure correct format
    base_url = server_url.rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    url = f"{base_url}/{topic}"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Get batch content, use ntfy's 4KB limit, reserve space for batch header
    ntfy_batch_size = 3800
    header_reserve = _get_max_batch_header_size("ntfy")
    batches = split_content_into_batches(
        report_data, "ntfy", update_info, max_bytes=ntfy_batch_size - header_reserve, mode=mode
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, "ntfy", ntfy_batch_size)

    total_batches = len(batches)
    print(f"ntfy message split into {total_batches} batches [{report_type}]")

    # Reverse batch order for correct display in ntfy client
    # ntfy shows newest messages on top, so we push from last batch
    reversed_batches = list(reversed(batches))

    print(f"ntfy will push in reverse order (last batch first) for correct client display")

    # Send batch by batch (reverse order)
    success_count = 0
    for idx, batch_content in enumerate(reversed_batches, 1):
        # Calculate correct batch number (from user's perspective)
        actual_batch_num = total_batches - idx + 1

        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"Sendingntfy batch {actual_batch_num}/{total_batches} (push order: {idx}/{total_batches}), size:{batch_size} bytes [{report_type}]"
        )

        # Check message size, ensure no more than 4KB
        if batch_size > 4096:
            print(f"Warning:ntfy batch {actual_batch_num} batch message too large ({batch_size} bytes), may be rejected")

        # Update batch identifier in headers
        current_headers = headers.copy()
        if total_batches > 1:
            current_headers["Title"] = (
                f"{report_type_en} ({actual_batch_num}/{total_batches})"
            )

        try:
            response = requests.post(
                url,
                headers=current_headers,
                data=batch_content.encode("utf-8"),
                proxies=proxies,
                timeout=30,
            )

            if response.status_code == 200:
                print(f"ntfy batch {actual_batch_num}/{total_batches} sent successfully [{report_type}]")
                success_count += 1
                if idx < total_batches:
                    # Public servers recommend 2-3 seconds, self-hosted can be shorter
                    interval = 2 if "ntfy.sh" in server_url else 1
                    time.sleep(interval)
            elif response.status_code == 429:
                print(
                    f"ntfy batch {actual_batch_num}/{total_batches} rate limited [{report_type}], waiting to retry"
                )
                time.sleep(10)  # Wait 10 seconds before retry
                # Retry once
                retry_response = requests.post(
                    url,
                    headers=current_headers,
                    data=batch_content.encode("utf-8"),
                    proxies=proxies,
                    timeout=30,
                )
                if retry_response.status_code == 200:
                    print(f"ntfy batch {actual_batch_num}/{total_batches} retry successful [{report_type}]")
                    success_count += 1
                else:
                    print(
                        f"ntfy batch {actual_batch_num}/{total_batches} retry failed,status code:{retry_response.status_code}"
                    )
            elif response.status_code == 413:
                print(
                    f"ntfy batch {actual_batch_num}/{total_batches} batch rejected as too large [{report_type}], message size:{batch_size} bytes"
                )
            else:
                print(
                    f"ntfy batch {actual_batch_num}/{total_batches} failed [{report_type}]，status code:{response.status_code}"
                )
                try:
                    print(f"Error details:{response.text}")
                except:
                    pass

        except requests.exceptions.ConnectTimeout:
            print(f"ntfy batch {actual_batch_num}/{total_batches} connection timeout [{report_type}]")
        except requests.exceptions.ReadTimeout:
            print(f"ntfy batch {actual_batch_num}/{total_batches} read timeout [{report_type}]")
        except requests.exceptions.ConnectionError as e:
            print(f"ntfy batch {actual_batch_num}/{total_batches} connection error [{report_type}]：{e}")
        except Exception as e:
            print(f"ntfy batch {actual_batch_num}/{total_batches} batches exception [{report_type}]：{e}")

    # Determine overall sending success
    if success_count == total_batches:
        print(f"ntfyall {total_batches} batches completed [{report_type}]")
        return True
    elif success_count > 0:
        print(f"ntfypartial success:{success_count}/{total_batches} batches [{report_type}]")
        return True  # Partial success is also considered success
    else:
        print(f"ntfysending completely failed [{report_type}]")
        return False


def send_to_bark(
    bark_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to Bark (supports batch sending, uses markdown format)"""
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Parse Bark URL, extract device_key and API endpoint
    # Bark URL format: https://api.day.app/device_key or https://bark.day.app/device_key
    from urllib.parse import urlparse

    parsed_url = urlparse(bark_url)
    device_key = parsed_url.path.strip('/').split('/')[0] if parsed_url.path else None

    if not device_key:
        print(f"Bark URL format error, unable to extract device_key: {bark_url}")
        return False

    # Build correct API endpoint
    api_endpoint = f"{parsed_url.scheme}://{parsed_url.netloc}/push"

    # Get batch content (Bark limit is 3600 bytes to avoid 413 error), reserve space for batch header
    bark_batch_size = CONFIG["BARK_BATCH_SIZE"]
    header_reserve = _get_max_batch_header_size("bark")
    batches = split_content_into_batches(
        report_data, "bark", update_info, max_bytes=bark_batch_size - header_reserve, mode=mode
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, "bark", bark_batch_size)

    total_batches = len(batches)
    print(f"Bark message split into {total_batches} batches [{report_type}]")

    # Reverse batch order for correct display in Bark client
    # Bark shows newest messages on top, so we push from last batch
    reversed_batches = list(reversed(batches))

    print(f"Bark will push in reverse order (last batch first) for correct client display")

    # Send batch by batch (reverse order)
    success_count = 0
    for idx, batch_content in enumerate(reversed_batches, 1):
        # Calculate correct batch number (from user's perspective)
        actual_batch_num = total_batches - idx + 1

        batch_size = len(batch_content.encode("utf-8"))
        print(
            f"SendingBark batch {actual_batch_num}/{total_batches} (push order: {idx}/{total_batches}), size:{batch_size} bytes [{report_type}]"
        )

        # Check message size (Bark uses APNs, 4KB limit)
        if batch_size > 4096:
            print(
                f"Warning:Bark batch {actual_batch_num}/{total_batches} batch message too large ({batch_size} bytes), may be rejected"
            )

        # Build JSON payload
        payload = {
            "title": report_type,
            "markdown": batch_content,
            "device_key": device_key,
            "sound": "default",
            "group": "TrendRadar",
            "action": "none",  # Click notification goes to app without popup for easy reading
        }

        try:
            response = requests.post(
                api_endpoint,
                json=payload,
                proxies=proxies,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    print(f"Bark batch {actual_batch_num}/{total_batches} sent successfully [{report_type}]")
                    success_count += 1
                    # Interval between batches
                    if idx < total_batches:
                        time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                else:
                    print(
                        f"Bark batch {actual_batch_num}/{total_batches} failed [{report_type}]，error:{result.get('message', 'Unknown error')}"
                    )
            else:
                print(
                    f"Bark batch {actual_batch_num}/{total_batches} failed [{report_type}]，status code:{response.status_code}"
                )
                try:
                    print(f"Error details:{response.text}")
                except:
                    pass

        except requests.exceptions.ConnectTimeout:
            print(f"Bark batch {actual_batch_num}/{total_batches} connection timeout [{report_type}]")
        except requests.exceptions.ReadTimeout:
            print(f"Bark batch {actual_batch_num}/{total_batches} read timeout [{report_type}]")
        except requests.exceptions.ConnectionError as e:
            print(f"Bark batch {actual_batch_num}/{total_batches} connection error [{report_type}]：{e}")
        except Exception as e:
            print(f"Bark batch {actual_batch_num}/{total_batches} batches exception [{report_type}]：{e}")

    # Determine overall sending success
    if success_count == total_batches:
        print(f"Barkall {total_batches} batches completed [{report_type}]")
        return True
    elif success_count > 0:
        print(f"Barkpartial success:{success_count}/{total_batches} batches [{report_type}]")
        return True  # Partial success is also considered success
    else:
        print(f"Barksending completely failed [{report_type}]")
        return False


def convert_markdown_to_mrkdwn(content: str) -> str:
    """
    Convert standard Markdown to Slack's mrkdwn format

    Conversion rules:
    - **bold** → *bold*
    - [text](url) → <url|text>
    - Keep other formats (code blocks, lists, etc.)
    """
    # 1. Convert link format: [text](url) → <url|text>
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', content)

    # 2. Convert bold: **text** → *text*
    content = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', content)

    return content


def send_to_slack(
    webhook_url: str,
    report_data: Dict,
    report_type: str,
    update_info: Optional[Dict] = None,
    proxy_url: Optional[str] = None,
    mode: str = "daily",
) -> bool:
    """Send to Slack (supports batch sending, uses mrkdwn format)"""
    headers = {"Content-Type": "application/json"}
    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    # Get batch content (use Slack batch size), reserve space for batch header
    slack_batch_size = CONFIG["SLACK_BATCH_SIZE"]
    header_reserve = _get_max_batch_header_size("slack")
    batches = split_content_into_batches(
        report_data, "slack", update_info, max_bytes=slack_batch_size - header_reserve, mode=mode
    )

    # Add batch headers uniformly (space already reserved, won't exceed limit)
    batches = add_batch_headers(batches, "slack", slack_batch_size)

    print(f"Slack message split into {len(batches)} batches [{report_type}]")

    # Send batch by batch
    for i, batch_content in enumerate(batches, 1):
        # Convert Markdown to mrkdwn format
        mrkdwn_content = convert_markdown_to_mrkdwn(batch_content)

        batch_size = len(mrkdwn_content.encode("utf-8"))
        print(
            f"SendingSlack batch {i}/{len(batches)} , size:{batch_size} bytes [{report_type}]"
        )

        # Build Slack payload (use simple text field, supports mrkdwn)
        payload = {
            "text": mrkdwn_content
        }

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )

            # Slack Incoming Webhooks returns "ok" text on success
            if response.status_code == 200 and response.text == "ok":
                print(f"Slack batch {i}/{len(batches)} sent successfully [{report_type}]")
                # Interval between batches
                if i < len(batches):
                    time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
            else:
                error_msg = response.text if response.text else f"status code:{response.status_code}"
                print(
                    f"Slack batch {i}/{len(batches)} failed [{report_type}]，error:{error_msg}"
                )
                return False
        except Exception as e:
            print(f"Slack batch {i}/{len(batches)} error [{report_type}]：{e}")
            return False

    print(f"Slackall {len(batches)} batches completed [{report_type}]")
    return True


# === Main Analyzer ===
class NewsAnalyzer:
    """News Analyzer"""

    # Mode strategy definitions
    MODE_STRATEGIES = {
        "incremental": {
            "mode_name": "Incremental Mode",
            "description": "Incremental Mode (only new news, skip push if none)",
            "realtime_report_type": "Realtime Incremental",
            "summary_report_type": "Daily Summary",
            "should_send_realtime": True,
            "should_generate_summary": True,
            "summary_mode": "daily",
        },
        "current": {
            "mode_name": "Current Ranking Mode",
            "description": "Current Ranking Mode (current ranking + new news + scheduled push)",
            "realtime_report_type": "Realtime Current Ranking",
            "summary_report_type": "Current Ranking",
            "should_send_realtime": True,
            "should_generate_summary": True,
            "summary_mode": "current",
        },
        "daily": {
            "mode_name": "Daily Summary Mode",
            "description": "Daily Summary Mode (all matched news + new news + scheduled push)",
            "realtime_report_type": "",
            "summary_report_type": "Daily Summary",
            "should_send_realtime": False,
            "should_generate_summary": True,
            "summary_mode": "daily",
        },
    }

    def __init__(self):
        self.request_interval = CONFIG["REQUEST_INTERVAL"]
        self.report_mode = CONFIG["REPORT_MODE"]
        self.rank_threshold = CONFIG["RANK_THRESHOLD"]
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker_container = self._detect_docker_environment()
        self.update_info = None
        self.proxy_url = None
        self._setup_proxy()
        self.data_fetcher = DataFetcher(self.proxy_url)

        if self.is_github_actions:
            self._check_version_update()

    def _detect_docker_environment(self) -> bool:
        """Detect if running in Docker container"""
        try:
            if os.environ.get("DOCKER_CONTAINER") == "true":
                return True

            if os.path.exists("/.dockerenv"):
                return True

            return False
        except Exception:
            return False

    def _should_open_browser(self) -> bool:
        """Determine if browser should be opened"""
        return not self.is_github_actions and not self.is_docker_container

    def _setup_proxy(self) -> None:
        """Setup proxy configuration"""
        if not self.is_github_actions and CONFIG["USE_PROXY"]:
            self.proxy_url = CONFIG["DEFAULT_PROXY"]
            print("Local environment, using proxy")
        elif not self.is_github_actions and not CONFIG["USE_PROXY"]:
            print("Local environment, proxy disabled")
        else:
            print("GitHub Actions environment, proxy not used")

    def _check_version_update(self) -> None:
        """Check for version updates"""
        try:
            need_update, remote_version = check_version_update(
                VERSION, CONFIG["VERSION_CHECK_URL"], self.proxy_url
            )

            if need_update and remote_version:
                self.update_info = {
                    "current_version": VERSION,
                    "remote_version": remote_version,
                }
                print(f"New version available: {remote_version} (current: {VERSION})")
            else:
                print("Version check complete, already on latest version")
        except Exception as e:
            print(f"Version check failed: {e}")

    def _get_mode_strategy(self) -> Dict:
        """Get strategy config for current mode"""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_notification_configured(self) -> bool:
        """Check if any notification channel is configured"""
        return any(
            [
                CONFIG["FEISHU_WEBHOOK_URL"],
                CONFIG["DINGTALK_WEBHOOK_URL"],
                CONFIG["WEWORK_WEBHOOK_URL"],
                (CONFIG["TELEGRAM_BOT_TOKEN"] and CONFIG["TELEGRAM_CHAT_ID"]),
                (
                    CONFIG["EMAIL_FROM"]
                    and CONFIG["EMAIL_PASSWORD"]
                    and CONFIG["EMAIL_TO"]
                ),
                (CONFIG["NTFY_SERVER_URL"] and CONFIG["NTFY_TOPIC"]),
                CONFIG["BARK_URL"],
                CONFIG["SLACK_WEBHOOK_URL"],
            ]
        )

    def _has_valid_content(
        self, stats: List[Dict], new_titles: Optional[Dict] = None
    ) -> bool:
        """Check if there is valid news content"""
        if self.report_mode in ["incremental", "current"]:
            # In incremental/current mode, having stats means matching news exists
            return any(stat["count"] > 0 for stat in stats)
        else:
            # In daily summary mode, check for matched keywords or new news
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            has_new_news = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            return has_matched_news or has_new_news

    def _load_analysis_data(
        self,
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, List, List]]:
        """Unified data loading and preprocessing, filter by current platform list"""
        try:
            # Get current configured platform ID list
            current_platform_ids = []
            for platform in CONFIG["PLATFORMS"]:
                current_platform_ids.append(platform["id"])

            print(f"Current monitored platforms: {current_platform_ids}")

            all_results, id_to_name, title_info = read_all_today_titles(
                current_platform_ids
            )

            if not all_results:
                print("No data found for today")
                return None

            total_titles = sum(len(titles) for titles in all_results.values())
            print(f"Loaded {total_titles} titles (filtered by current platforms)")

            new_titles = detect_latest_new_titles(current_platform_ids)
            word_groups, filter_words = load_frequency_words()

            return (
                all_results,
                id_to_name,
                title_info,
                new_titles,
                word_groups,
                filter_words,
            )
        except Exception as e:
            print(f"Data loading failed: {e}")
            return None

    def _prepare_current_title_info(self, results: Dict, time_info: str) -> Dict:
        """Build title info from current crawl results"""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, title_data in titles_data.items():
                ranks = title_data.get("ranks", [])
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        return title_info

    def _run_analysis_pipeline(
        self,
        data_source: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        is_daily_summary: bool = False,
    ) -> Tuple[List[Dict], str]:
        """Unified analysis pipeline: data processing → statistics → HTML generation"""

        # Statistics calculation
        stats, total_titles = count_word_frequency(
            data_source,
            word_groups,
            filter_words,
            id_to_name,
            title_info,
            self.rank_threshold,
            new_titles,
            mode=mode,
        )

        # HTML generation
        html_file = generate_html_report(
            stats,
            total_titles,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            is_daily_summary=is_daily_summary,
            update_info=self.update_info if CONFIG["SHOW_VERSION_UPDATE"] else None,
        )

        return stats, html_file

    def _send_notification_if_needed(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        html_file_path: Optional[str] = None,
    ) -> bool:
        """Unified notification sending logic with all condition checks"""
        has_notification = self._has_notification_configured()

        if (
            CONFIG["ENABLE_NOTIFICATION"]
            and has_notification
            and self._has_valid_content(stats, new_titles)
        ):
            send_to_notifications(
                stats,
                failed_ids or [],
                report_type,
                new_titles,
                id_to_name,
                self.update_info,
                self.proxy_url,
                mode=mode,
                html_file_path=html_file_path,
            )
            return True
        elif CONFIG["ENABLE_NOTIFICATION"] and not has_notification:
            print("⚠️ Warning: Notification enabled but no channels configured, skipping")
        elif not CONFIG["ENABLE_NOTIFICATION"]:
            print(f"Skipping {report_type} notification: notifications disabled")
        elif (
            CONFIG["ENABLE_NOTIFICATION"]
            and has_notification
            and not self._has_valid_content(stats, new_titles)
        ):
            mode_strategy = self._get_mode_strategy()
            if "realtime" in report_type.lower():
                print(
                    f"Skipping realtime notification: no matching news in {mode_strategy['mode_name']}"
                )
            else:
                print(
                    f"Skipping {mode_strategy['summary_report_type']} notification: no valid news content"
                )

        return False

    def _generate_summary_report(self, mode_strategy: Dict) -> Optional[str]:
        """Generate summary report (with notifications)"""
        summary_type = (
            "Current Ranking Summary" if mode_strategy["summary_mode"] == "current" else "Daily Summary"
        )
        print(f"Generating {summary_type} report...")

        # Load analysis data
        analysis_data = self._load_analysis_data()
        if not analysis_data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = (
            analysis_data
        )

        # Run analysis pipeline
        stats, html_file = self._run_analysis_pipeline(
            all_results,
            mode_strategy["summary_mode"],
            title_info,
            new_titles,
            word_groups,
            filter_words,
            id_to_name,
            is_daily_summary=True,
        )

        print(f"{summary_type} report generated: {html_file}")

        # Send notification
        self._send_notification_if_needed(
            stats,
            mode_strategy["summary_report_type"],
            mode_strategy["summary_mode"],
            failed_ids=[],
            new_titles=new_titles,
            id_to_name=id_to_name,
            html_file_path=html_file,
        )

        return html_file

    def _generate_summary_html(self, mode: str = "daily") -> Optional[str]:
        """Generate summary HTML"""
        summary_type = "Current Ranking Summary" if mode == "current" else "Daily Summary"
        print(f"Generating {summary_type} HTML...")

        # Load analysis data
        analysis_data = self._load_analysis_data()
        if not analysis_data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = (
            analysis_data
        )

        # Run analysis pipeline
        _, html_file = self._run_analysis_pipeline(
            all_results,
            mode,
            title_info,
            new_titles,
            word_groups,
            filter_words,
            id_to_name,
            is_daily_summary=True,
        )

        print(f"{summary_type} HTML generated: {html_file}")
        return html_file

    def _initialize_and_check_config(self) -> None:
        """General initialization and config check"""
        now = get_beijing_time()
        print(f"Current Beijing time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not CONFIG["ENABLE_CRAWLER"]:
            print("Crawler disabled (ENABLE_CRAWLER=False), exiting")
            return

        has_notification = self._has_notification_configured()
        if not CONFIG["ENABLE_NOTIFICATION"]:
            print("Notifications disabled (ENABLE_NOTIFICATION=False), crawling only")
        elif not has_notification:
            print("No notification channels configured, crawling only")
        else:
            print("Notifications enabled, will send notifications")

        mode_strategy = self._get_mode_strategy()
        print(f"Report mode: {self.report_mode}")
        print(f"Run mode: {mode_strategy['description']}")

    def _crawl_data(self) -> Tuple[Dict, Dict, List]:
        """Execute data crawling"""
        ids = []
        for platform in CONFIG["PLATFORMS"]:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])

        print(
            f"Configured platforms: {[p.get('name', p['id']) for p in CONFIG['PLATFORMS']]}"
        )
        print(f"Starting crawl, request interval {self.request_interval} ms")
        ensure_directory_exists("output")

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval
        )

        title_file = save_titles_to_file(results, id_to_name, failed_ids)
        print(f"Titles saved to: {title_file}")

        return results, id_to_name, failed_ids

    def _execute_mode_strategy(
        self, mode_strategy: Dict, results: Dict, id_to_name: Dict, failed_ids: List
    ) -> Optional[str]:
        """Execute mode-specific logic"""
        # Get current platform ID list
        current_platform_ids = [platform["id"] for platform in CONFIG["PLATFORMS"]]

        new_titles = detect_latest_new_titles(current_platform_ids)
        time_info = Path(save_titles_to_file(results, id_to_name, failed_ids)).stem
        word_groups, filter_words = load_frequency_words()

        # In current mode, realtime push needs full historical data for statistics
        if self.report_mode == "current":
            # Load full historical data (filtered by current platforms)
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                ) = analysis_data

                print(
                    f"Current mode: using filtered historical data, platforms: {list(all_results.keys())}"
                )

                stats, html_file = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}

                print(f"HTML report generated: {html_file}")

                # Send realtime notification (using full historical data stats)
                summary_html = None
                if mode_strategy["should_send_realtime"]:
                    self._send_notification_if_needed(
                        stats,
                        mode_strategy["realtime_report_type"],
                        self.report_mode,
                        failed_ids=failed_ids,
                        new_titles=historical_new_titles,
                        id_to_name=combined_id_to_name,
                        html_file_path=html_file,
                    )
            else:
                print("❌ Critical error: cannot read just-saved data file")
                raise RuntimeError("Data consistency check failed: read failed after save")
        else:
            title_info = self._prepare_current_title_info(results, time_info)
            stats, html_file = self._run_analysis_pipeline(
                results,
                self.report_mode,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                id_to_name,
                failed_ids=failed_ids,
            )
            print(f"HTML report generated: {html_file}")

            # Send realtime notification (if needed)
            summary_html = None
            if mode_strategy["should_send_realtime"]:
                self._send_notification_if_needed(
                    stats,
                    mode_strategy["realtime_report_type"],
                    self.report_mode,
                    failed_ids=failed_ids,
                    new_titles=new_titles,
                    id_to_name=id_to_name,
                    html_file_path=html_file,
                )

        # Generate summary report (if needed)
        summary_html = None
        if mode_strategy["should_generate_summary"]:
            if mode_strategy["should_send_realtime"]:
                # If realtime notification sent, summary only generates HTML
                summary_html = self._generate_summary_html(
                    mode_strategy["summary_mode"]
                )
            else:
                # Daily mode: generate summary report and send notification
                summary_html = self._generate_summary_report(mode_strategy)

        # Open browser (non-container environments only)
        if self._should_open_browser() and html_file:
            if summary_html:
                summary_url = "file://" + str(Path(summary_html).resolve())
                print(f"Opening summary report: {summary_url}")
                webbrowser.open(summary_url)
            else:
                file_url = "file://" + str(Path(html_file).resolve())
                print(f"Opening HTML report: {file_url}")
                webbrowser.open(file_url)
        elif self.is_docker_container and html_file:
            if summary_html:
                print(f"Summary report generated (Docker): {summary_html}")
            else:
                print(f"HTML report generated (Docker): {html_file}")

        return summary_html

    def run(self) -> None:
        """Execute analysis workflow"""
        try:
            self._initialize_and_check_config()

            mode_strategy = self._get_mode_strategy()

            results, id_to_name, failed_ids = self._crawl_data()

            self._execute_mode_strategy(mode_strategy, results, id_to_name, failed_ids)

        except Exception as e:
            print(f"Analysis workflow error: {e}")
            raise


def main():
    try:
        analyzer = NewsAnalyzer()
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ Config file error: {e}")
        print("\nPlease ensure these files exist:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\nRefer to project documentation for configuration")
    except Exception as e:
        print(f"❌ Runtime error: {e}")
        raise


if __name__ == "__main__":
    main()
