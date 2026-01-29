"""
Centralized configuration with full .env support
"""
from os import path
import os
from json import load
import json
import typing
from dotenv import load_dotenv

# Load .env file if present
load_dotenv(path.join(path.dirname(path.abspath(__file__)), '.env'))

PROJECT_ROOT = path.dirname(path.abspath(__file__))

# =============== FACEBOOK CREDENTIALS ===============
def _load_credentials_from_file():
    """Load Facebook credentials from sessions/facebook-credentials.json if present."""
    try:
        creds_path = path.join(PROJECT_ROOT, 'sessions', 'facebook-credentials.json')
        if path.exists(creds_path):
            with open(creds_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                email = data.get('email') or data.get('username')
                password = data.get('password')
                return email, password
    except Exception:
        pass
    return None, None

_file_email, _file_password = _load_credentials_from_file()
FACEBOOK_EMAIL = os.environ.get("FACEBOOK_EMAIL") or _file_email
FACEBOOK_PASSWORD = os.environ.get("FACEBOOK_PASSWORD") or _file_password

# =============== SERVER SETTINGS ===============
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(24).hex()

# =============== DASHBOARD AUTH ===============
DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME") or "admin"
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD")

# =============== PROXY ===============
PROXY_URL = os.environ.get("PROXY_URL") or None

# =============== POSTING BEHAVIOR ===============
HEADLESS_ONLY = os.environ.get("HEADLESS_ONLY", "1") not in ("0", "false", "False")
DRY_RUN = os.environ.get("DRY_RUN", "0") in ("1", "true", "True")
RETRY_PER_GROUP = int(os.environ.get("RETRY_PER_GROUP", "1"))
MIN_DELAY_BETWEEN_POSTS = int(os.environ.get("MIN_DELAY_BETWEEN_POSTS", "30"))
MAX_DELAY_BETWEEN_POSTS = int(os.environ.get("MAX_DELAY_BETWEEN_POSTS", "120"))

# =============== RATE LIMITING ===============
RATE_LIMIT_POSTS_PER_HOUR = int(os.environ.get("RATE_LIMIT_POSTS_PER_HOUR", "10"))
RATE_LIMIT_GROUPS_PER_POST = int(os.environ.get("RATE_LIMIT_GROUPS_PER_POST", "20"))

# =============== SMART DELAYS ===============
USE_GAUSSIAN_DELAYS = os.environ.get("USE_GAUSSIAN_DELAYS", "true").lower() == "true"
ACTIVITY_HOURS_START = int(os.environ.get("ACTIVITY_HOURS_START", "8"))
ACTIVITY_HOURS_END = int(os.environ.get("ACTIVITY_HOURS_END", "22"))

# =============== SESSION MONITORING ===============
SESSION_CHECK_INTERVAL_MINUTES = int(os.environ.get("SESSION_CHECK_INTERVAL_MINUTES", "30"))
SESSION_ALERT_WEBHOOK = os.environ.get("SESSION_ALERT_WEBHOOK") or None

# =============== BACKUP SETTINGS ===============
ENABLE_AUTO_BACKUP = os.environ.get("ENABLE_AUTO_BACKUP", "true").lower() == "true"
BACKUP_INTERVAL_HOURS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "24"))
BACKUP_MAX_FILES = int(os.environ.get("BACKUP_MAX_FILES", "7"))

# =============== TIMEZONE ===============
TIMEZONE = os.environ.get("TIMEZONE", "UTC")

# =============== LOGGING ===============
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("LOG_FILE", "logs/app.log")
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", "10485760"))  # 10MB
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "5"))

# =============== ERROR MONITORING ===============
SENTRY_DSN = os.environ.get("SENTRY_DSN") or None

# =============== FEATURE FLAGS ===============
ENABLE_SCHEDULING = os.environ.get("ENABLE_SCHEDULING", "true").lower() == "true"
ENABLE_SPINTAX = os.environ.get("ENABLE_SPINTAX", "true").lower() == "true"
ENABLE_MULTI_ACCOUNT = os.environ.get("ENABLE_MULTI_ACCOUNT", "true").lower() == "true"
ENABLE_MEDIA_LIBRARY = os.environ.get("ENABLE_MEDIA_LIBRARY", "true").lower() == "true"
ENABLE_CONTENT_TEMPLATES = os.environ.get("ENABLE_CONTENT_TEMPLATES", "true").lower() == "true"

# Aliases for backward compatibility
SERVER_PORT = PORT
SERVER_HOST = HOST
DEBUG_MODE = DEBUG

# =============== SOCIAL MAPS ===============
SOCIAL_MAPS = {
    "facebook": {
        "login": "https://m.facebook.com/login",
        "filename": "facebook-cookies.json",
    }
}


def get_sources_list() -> typing.List:
    """Load groups from groups.json"""
    with open(f"{PROJECT_ROOT}/groups.json", "r", encoding="utf-8") as sources_file:
        return load(sources_file)


def get_config_summary() -> dict:
    """Return a summary of current configuration (safe for logging)"""
    return {
        "host": HOST,
        "port": PORT,
        "debug": DEBUG,
        "headless_only": HEADLESS_ONLY,
        "dry_run": DRY_RUN,
        "rate_limit_posts_per_hour": RATE_LIMIT_POSTS_PER_HOUR,
        "rate_limit_groups_per_post": RATE_LIMIT_GROUPS_PER_POST,
        "use_gaussian_delays": USE_GAUSSIAN_DELAYS,
        "activity_hours": f"{ACTIVITY_HOURS_START}-{ACTIVITY_HOURS_END}",
        "timezone": TIMEZONE,
        "enable_scheduling": ENABLE_SCHEDULING,
        "enable_multi_account": ENABLE_MULTI_ACCOUNT,
        "has_proxy": bool(PROXY_URL),
        "has_sentry": bool(SENTRY_DSN),
    }
