"""
Rate limiting and smart delay utilities
"""
import time
import random
import math
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from collections import defaultdict
import threading

try:
    from config import (
        RATE_LIMIT_POSTS_PER_HOUR,
        RATE_LIMIT_GROUPS_PER_POST,
        USE_GAUSSIAN_DELAYS,
        ACTIVITY_HOURS_START,
        ACTIVITY_HOURS_END,
        MIN_DELAY_BETWEEN_POSTS,
        MAX_DELAY_BETWEEN_POSTS,
    )
except ImportError:
    RATE_LIMIT_POSTS_PER_HOUR = 10
    RATE_LIMIT_GROUPS_PER_POST = 20
    USE_GAUSSIAN_DELAYS = True
    ACTIVITY_HOURS_START = 8
    ACTIVITY_HOURS_END = 22
    MIN_DELAY_BETWEEN_POSTS = 30
    MAX_DELAY_BETWEEN_POSTS = 120


class RateLimiter:
    """
    Per-account rate limiting to avoid Facebook detection
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        # account_id -> list of timestamps
        self._post_history: Dict[str, list] = defaultdict(list)
        # account_id -> count of posts in current hour
        self._hourly_counts: Dict[str, int] = defaultdict(int)
        self._last_reset: Dict[str, datetime] = {}
    
    def _cleanup_old_entries(self, account_id: str):
        """Remove entries older than 1 hour"""
        cutoff = datetime.now() - timedelta(hours=1)
        self._post_history[account_id] = [
            ts for ts in self._post_history[account_id]
            if ts > cutoff
        ]
    
    def can_post(self, account_id: str = "default") -> tuple[bool, str]:
        """
        Check if posting is allowed for this account
        
        Returns:
            (allowed, reason) tuple
        """
        if RATE_LIMIT_POSTS_PER_HOUR <= 0:
            return True, "Rate limiting disabled"
        
        with self._lock:
            self._cleanup_old_entries(account_id)
            
            count = len(self._post_history[account_id])
            if count >= RATE_LIMIT_POSTS_PER_HOUR:
                oldest = min(self._post_history[account_id])
                wait_until = oldest + timedelta(hours=1)
                wait_seconds = (wait_until - datetime.now()).total_seconds()
                return False, f"Rate limit reached ({count}/{RATE_LIMIT_POSTS_PER_HOUR}). Try again in {int(wait_seconds/60)} minutes."
            
            return True, f"OK ({count}/{RATE_LIMIT_POSTS_PER_HOUR} posts this hour)"
    
    def record_post(self, account_id: str = "default"):
        """Record a post for rate limiting"""
        with self._lock:
            self._post_history[account_id].append(datetime.now())
    
    def get_remaining_posts(self, account_id: str = "default") -> int:
        """Get number of remaining posts allowed this hour"""
        if RATE_LIMIT_POSTS_PER_HOUR <= 0:
            return 999
        
        with self._lock:
            self._cleanup_old_entries(account_id)
            return max(0, RATE_LIMIT_POSTS_PER_HOUR - len(self._post_history[account_id]))
    
    def check_groups_limit(self, group_count: int) -> tuple[bool, str, int]:
        """
        Check if the number of groups is within limits
        
        Returns:
            (allowed, reason, adjusted_count) tuple
        """
        if RATE_LIMIT_GROUPS_PER_POST <= 0:
            return True, "Group limit disabled", group_count
        
        if group_count > RATE_LIMIT_GROUPS_PER_POST:
            return False, f"Too many groups ({group_count}). Max allowed: {RATE_LIMIT_GROUPS_PER_POST}", RATE_LIMIT_GROUPS_PER_POST
        
        return True, f"OK ({group_count}/{RATE_LIMIT_GROUPS_PER_POST} groups)", group_count


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_smart_delay(min_seconds: int = None, max_seconds: int = None) -> float:
    """
    Get a human-like delay using Gaussian distribution
    
    Features:
    - Gaussian distribution for natural timing
    - Longer delays during off-hours
    - Random micro-variations
    """
    min_s = min_seconds or MIN_DELAY_BETWEEN_POSTS
    max_s = max_seconds or MAX_DELAY_BETWEEN_POSTS
    
    if USE_GAUSSIAN_DELAYS:
        # Gaussian distribution centered between min and max
        mean = (min_s + max_s) / 2
        std_dev = (max_s - min_s) / 4  # ~95% within range
        
        delay = random.gauss(mean, std_dev)
        delay = max(min_s, min(max_s, delay))  # Clamp to range
    else:
        # Simple uniform distribution
        delay = random.uniform(min_s, max_s)
    
    # Add micro-variations (±10%)
    variation = delay * random.uniform(-0.1, 0.1)
    delay += variation
    
    # Increase delay during off-hours
    current_hour = datetime.now().hour
    if current_hour < ACTIVITY_HOURS_START or current_hour >= ACTIVITY_HOURS_END:
        delay *= 1.5  # 50% longer delays outside activity hours
    
    return max(min_s, delay)


def is_activity_hours() -> bool:
    """Check if current time is within activity hours"""
    current_hour = datetime.now().hour
    return ACTIVITY_HOURS_START <= current_hour < ACTIVITY_HOURS_END


def get_next_activity_window() -> datetime:
    """Get the start of the next activity window"""
    now = datetime.now()
    current_hour = now.hour
    
    if current_hour < ACTIVITY_HOURS_START:
        # Today, at activity start
        return now.replace(hour=ACTIVITY_HOURS_START, minute=0, second=0, microsecond=0)
    elif current_hour >= ACTIVITY_HOURS_END:
        # Tomorrow, at activity start
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=ACTIVITY_HOURS_START, minute=0, second=0, microsecond=0)
    else:
        # Currently in activity hours
        return now


def delay_with_progress(seconds: float, callback: Optional[Callable[[float], None]] = None):
    """
    Sleep with progress reporting
    
    Args:
        seconds: Total seconds to wait
        callback: Optional callback(progress) where progress is 0.0-1.0
    """
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed >= seconds:
            break
        
        if callback:
            progress = min(1.0, elapsed / seconds)
            callback(progress)
        
        # Sleep in small increments for responsiveness
        remaining = seconds - elapsed
        time.sleep(min(1.0, remaining))
    
    if callback:
        callback(1.0)


def jitter(base_seconds: float, factor: float = 0.2) -> float:
    """Add random jitter to a delay"""
    variation = base_seconds * factor
    return base_seconds + random.uniform(-variation, variation)
