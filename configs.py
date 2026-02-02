"""
Configuration file for FB Auto Poster
"""
import os
import json

# Project paths
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(PROJECT_ROOT, 'sessions')
MEDIA_DIR = os.path.join(PROJECT_ROOT, 'media_library')
LOGS_DIR = os.path.join(PROJECT_ROOT, 'logs')
BACKUPS_DIR = os.path.join(PROJECT_ROOT, 'backups')

# Dashboard credentials
DASHBOARD_USERNAME = 'admin'
DASHBOARD_PASSWORD = 'password123'

# Database
DATABASE_PATH = os.path.join(PROJECT_ROOT, 'posts.db')

# Load Facebook credentials from file or environment
def _load_fb_credentials():
    """Load Facebook credentials from sessions/facebook-credentials.json if present."""
    try:
        creds_path = os.path.join(PROJECT_ROOT, 'sessions', 'facebook-credentials.json')
        if os.path.exists(creds_path):
            with open(creds_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                email = data.get('email') or data.get('username')
                password = data.get('password')
                return email, password
    except Exception:
        pass
    return None, None

_file_email, _file_password = _load_fb_credentials()
FACEBOOK_EMAIL = os.environ.get("FACEBOOK_EMAIL") or _file_email
FACEBOOK_PASSWORD = os.environ.get("FACEBOOK_PASSWORD") or _file_password

# Ensure directories exist
for directory in [SESSIONS_DIR, MEDIA_DIR, LOGS_DIR, BACKUPS_DIR]:
    os.makedirs(directory, exist_ok=True)
