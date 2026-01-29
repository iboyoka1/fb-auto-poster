"""
Utility functions for enhanced Facebook posting bot
"""
import random
import re
import csv
from datetime import datetime, timedelta
from typing import List, Dict


def spin_text(text: str) -> str:
    """
    Process spintax text and return a random variation
    Example: "{Hello|Hi|Hey} {world|everyone}" -> "Hi everyone"
    """
    def replace_spin(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    # Keep spinning until no more spintax patterns found
    while re.search(r'\{([^{}]+)\}', text):
        text = re.sub(r'\{([^{}]+)\}', replace_spin, text)
    
    return text


def get_random_delay(min_seconds: int, max_seconds: int) -> int:
    """Get a random delay in seconds with human-like distribution"""
    # Use exponential distribution for more natural timing
    delay = random.expovariate(1.0 / ((min_seconds + max_seconds) / 2))
    delay = max(min_seconds, min(max_seconds, delay))
    return int(delay)


def format_time_remaining(seconds: int) -> str:
    """Format seconds into human-readable time"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def load_groups_from_csv(csv_file: str) -> List[Dict]:
    """
    Load groups from CSV file
    Expected format: name,username,status
    """
    groups = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                groups.append({
                    'name': row.get('name', ''),
                    'username': row.get('username', ''),
                    'status': row.get('status', 'active')
                })
        print(f"[+] Loaded {len(groups)} groups from CSV")
        return groups
    except Exception as e:
        print(f"[-] Error loading CSV: {e}")
        return []


def save_groups_to_csv(groups: List[Dict], csv_file: str) -> bool:
    """Save groups list to CSV file"""
    try:
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if groups:
                writer = csv.DictWriter(f, fieldnames=['name', 'username', 'status'])
                writer.writeheader()
                writer.writerows(groups)
        print(f"[+] Saved {len(groups)} groups to CSV")
        return True
    except Exception as e:
        print(f"[-] Error saving CSV: {e}")
        return False


def parse_schedule(schedule_str: str) -> datetime:
    """
    Parse schedule string to datetime
    Formats: "14:30", "2025-12-24 14:30", "30m" (30 minutes from now)
    """
    try:
        # Relative time (e.g., "30m", "2h")
        if schedule_str.endswith('m'):
            minutes = int(schedule_str[:-1])
            return datetime.now() + timedelta(minutes=minutes)
        elif schedule_str.endswith('h'):
            hours = int(schedule_str[:-1])
            return datetime.now() + timedelta(hours=hours)
        
        # Time only (today)
        if ':' in schedule_str and len(schedule_str) <= 5:
            time_parts = schedule_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            scheduled = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            if scheduled < datetime.now():
                scheduled += timedelta(days=1)
            return scheduled
        
        # Full datetime
        return datetime.strptime(schedule_str, "%Y-%m-%d %H:%M")
    
    except Exception as e:
        print(f"[-] Error parsing schedule: {e}")
        return None


def should_post_now(scheduled_time: datetime) -> bool:
    """Check if it's time to post"""
    if not scheduled_time:
        return True
    return datetime.now() >= scheduled_time


def validate_image_path(image_path: str) -> bool:
    """Validate if image path exists and is a valid image"""
    import os
    if not os.path.exists(image_path):
        return False
    
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ext = os.path.splitext(image_path)[1].lower()
    return ext in valid_extensions


def get_content_variations(base_content: str, count: int = 5) -> List[str]:
    """Generate multiple variations of content using spintax"""
    variations = []
    for _ in range(count):
        variation = spin_text(base_content)
        if variation not in variations:
            variations.append(variation)
    return variations
