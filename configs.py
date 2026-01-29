"""
Configuration file for FB Auto Poster
"""
import os

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

# Ensure directories exist
for directory in [SESSIONS_DIR, MEDIA_DIR, LOGS_DIR, BACKUPS_DIR]:
    os.makedirs(directory, exist_ok=True)
