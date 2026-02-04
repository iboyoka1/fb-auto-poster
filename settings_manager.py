"""
Settings Manager - Allows runtime configuration without code changes
Perfect for client customization
"""
import json
import os
from typing import Dict, Any

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(PROJECT_ROOT, 'app_settings.json')

# Default settings
DEFAULT_SETTINGS = {
    # Branding
    'app_name': 'FB Auto Poster',
    'primary_color': '#1877f2',
    
    # Posting behavior
    'min_delay': 30,
    'max_delay': 120,
    'posts_per_hour': 10,
    'groups_per_post': 20,
    'retry_count': 1,
    
    # Activity hours
    'activity_start': 8,
    'activity_end': 22,
    'timezone': 'UTC',
    
    # Features
    'enable_scheduling': True,
    'enable_spintax': True,
    'enable_media_library': True,
    'enable_templates': True,
    'use_gaussian_delays': True,
    
    # Session
    'session_check_interval': 30,
    'browser_locale': 'fr-FR',
    
    # Advanced
    'headless_mode': True,
    'debug_mode': False,
}


def load_settings() -> Dict[str, Any]:
    """Load settings from file, with defaults for missing keys"""
    settings = DEFAULT_SETTINGS.copy()
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    return settings


def save_settings(new_settings: Dict[str, Any]) -> bool:
    """Save settings to file"""
    try:
        # Merge with existing settings
        settings = load_settings()
        settings.update(new_settings)
        
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


def reset_settings() -> bool:
    """Reset settings to defaults"""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_SETTINGS, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error resetting settings: {e}")
        return False


def get_setting(key: str, default=None) -> Any:
    """Get a single setting value"""
    settings = load_settings()
    return settings.get(key, default)


def set_setting(key: str, value: Any) -> bool:
    """Set a single setting value"""
    return save_settings({key: value})


# Convenience getters for common settings
def get_app_name() -> str:
    return get_setting('app_name', 'FB Auto Poster')

def get_posting_delays() -> tuple:
    settings = load_settings()
    return (settings.get('min_delay', 30), settings.get('max_delay', 120))

def get_rate_limits() -> tuple:
    settings = load_settings()
    return (settings.get('posts_per_hour', 10), settings.get('groups_per_post', 20))

def get_activity_hours() -> tuple:
    settings = load_settings()
    return (settings.get('activity_start', 8), settings.get('activity_end', 22))

def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled"""
    feature_map = {
        'scheduling': 'enable_scheduling',
        'spintax': 'enable_spintax',
        'media_library': 'enable_media_library',
        'templates': 'enable_templates',
        'gaussian_delays': 'use_gaussian_delays',
    }
    key = feature_map.get(feature, f'enable_{feature}')
    return get_setting(key, True)
