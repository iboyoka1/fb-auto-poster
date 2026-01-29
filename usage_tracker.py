"""
Usage Tracking - Track application usage for analytics
"""
import os
import json
import sqlite3
from datetime import datetime
from configs import PROJECT_ROOT

TRACKING_DB = os.path.join(PROJECT_ROOT, 'usage_tracking.db')

class UsageTracker:
    """Track application usage for analytics and licensing"""
    
    def __init__(self):
        self.db_path = TRACKING_DB
        self._init_db()
    
    def _init_db(self):
        """Initialize tracking database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_stats (
                    id INTEGER PRIMARY KEY,
                    date TEXT,
                    posts_created INTEGER,
                    posts_scheduled INTEGER,
                    groups_used INTEGER,
                    auto_discover_runs INTEGER,
                    session_duration_minutes INTEGER,
                    features_used TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feature_usage (
                    id INTEGER PRIMARY KEY,
                    feature_name TEXT,
                    usage_count INTEGER,
                    last_used DATETIME,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS licensing (
                    id INTEGER PRIMARY KEY,
                    license_key TEXT UNIQUE,
                    activated BOOLEAN,
                    activation_date DATETIME,
                    expiration_date DATETIME,
                    max_posts INTEGER,
                    max_groups INTEGER,
                    posts_used INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database init error: {e}")
    
    def track_post(self, num_posts: int = 1, groups_count: int = 0):
        """Track post creation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                INSERT INTO usage_stats 
                (date, posts_created, groups_used) 
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    posts_created = posts_created + ?,
                    groups_used = groups_used + ?
            ''', (today, num_posts, groups_count, num_posts, groups_count))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Tracking error: {e}")
            return False
    
    def track_feature(self, feature_name: str):
        """Track feature usage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO feature_usage (feature_name, usage_count, last_used)
                VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(feature_name) DO UPDATE SET
                    usage_count = usage_count + 1,
                    last_used = CURRENT_TIMESTAMP
            ''', (feature_name,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Feature tracking error: {e}")
            return False
    
    def get_daily_stats(self, days: int = 30) -> dict:
        """Get usage statistics for last N days"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    SUM(posts_created) as total_posts,
                    SUM(posts_scheduled) as total_scheduled,
                    SUM(groups_used) as total_groups,
                    SUM(auto_discover_runs) as total_discovers,
                    COUNT(DISTINCT date) as active_days
                FROM usage_stats
                WHERE DATE(timestamp) >= DATE('now', '-' || ? || ' days')
            ''', (days,))
            
            result = cursor.fetchone()
            conn.close()
            
            return {
                'total_posts': result[0] or 0,
                'total_scheduled': result[1] or 0,
                'total_groups': result[2] or 0,
                'total_discovers': result[3] or 0,
                'active_days': result[4] or 0
            }
        except Exception as e:
            print(f"Stats error: {e}")
            return {}
    
    def get_feature_stats(self) -> dict:
        """Get feature usage statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT feature_name, usage_count, last_used
                FROM feature_usage
                ORDER BY usage_count DESC
            ''')
            
            features = {}
            for row in cursor.fetchall():
                features[row[0]] = {
                    'usage_count': row[1],
                    'last_used': row[2]
                }
            
            conn.close()
            return features
        except Exception as e:
            print(f"Feature stats error: {e}")
            return {}
    
    def activate_license(self, license_key: str, max_posts: int = 1000, max_groups: int = 100) -> bool:
        """Activate license key"""
        try:
            from datetime import timedelta
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            expiration = (datetime.now() + timedelta(days=365)).isoformat()
            
            cursor.execute('''
                INSERT INTO licensing 
                (license_key, activated, activation_date, expiration_date, max_posts, max_groups)
                VALUES (?, 1, CURRENT_TIMESTAMP, ?, ?, ?)
            ''', (license_key, expiration, max_posts, max_groups))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"License activation error: {e}")
            return False
    
    def check_license_valid(self, license_key: str) -> bool:
        """Check if license is still valid"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT activated, expiration_date FROM licensing
                WHERE license_key = ?
                AND activated = 1
                AND expiration_date > CURRENT_TIMESTAMP
            ''', (license_key,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result is not None
        except Exception as e:
            print(f"License check error: {e}")
            return False


# Global instance
usage_tracker = UsageTracker()
