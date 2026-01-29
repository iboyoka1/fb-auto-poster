"""
Analytics module for tracking posting performance
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

try:
    from config import PROJECT_ROOT
except ImportError:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(PROJECT_ROOT, "posts.db")


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_analytics_tables():
    """Initialize analytics tables if they don't exist"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Ensure post_analytics table exists
    c.execute('''
        CREATE TABLE IF NOT EXISTS post_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            group_name TEXT,
            posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    ''')
    
    # Group performance tracking
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_username TEXT UNIQUE,
            group_name TEXT,
            total_posts INTEGER DEFAULT 0,
            successful_posts INTEGER DEFAULT 0,
            failed_posts INTEGER DEFAULT 0,
            last_post_at DATETIME,
            avg_response_time_ms INTEGER DEFAULT 0
        )
    ''')
    
    # Daily stats aggregation
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            total_posts INTEGER DEFAULT 0,
            successful_posts INTEGER DEFAULT 0,
            failed_posts INTEGER DEFAULT 0,
            groups_posted INTEGER DEFAULT 0,
            avg_delay_seconds REAL DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()


init_analytics_tables()


class AnalyticsManager:
    """
    Comprehensive analytics for posting performance
    """
    
    def record_post_result(
        self,
        post_id: int,
        group_name: str,
        group_username: str,
        success: bool,
        error_message: str = None,
        response_time_ms: int = 0,
    ):
        """Record the result of posting to a group"""
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            # Record in post_analytics
            c.execute('''
                INSERT INTO post_analytics (post_id, group_name, success, error_message)
                VALUES (?, ?, ?, ?)
            ''', (post_id, group_name, 1 if success else 0, error_message))
            
            # Update group performance
            c.execute('''
                INSERT INTO group_performance (group_username, group_name, total_posts, successful_posts, failed_posts, last_post_at, avg_response_time_ms)
                VALUES (?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(group_username) DO UPDATE SET
                    total_posts = total_posts + 1,
                    successful_posts = successful_posts + ?,
                    failed_posts = failed_posts + ?,
                    last_post_at = ?,
                    avg_response_time_ms = (avg_response_time_ms + ?) / 2
            ''', (
                group_username, group_name,
                1 if success else 0, 0 if success else 1,
                datetime.now().isoformat(), response_time_ms,
                1 if success else 0, 0 if success else 1,
                datetime.now().isoformat(), response_time_ms
            ))
            
            # Update daily stats
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute('''
                INSERT INTO daily_stats (date, total_posts, successful_posts, failed_posts, groups_posted)
                VALUES (?, 1, ?, ?, 1)
                ON CONFLICT(date) DO UPDATE SET
                    total_posts = total_posts + 1,
                    successful_posts = successful_posts + ?,
                    failed_posts = failed_posts + ?,
                    groups_posted = groups_posted + 1
            ''', (
                today,
                1 if success else 0, 0 if success else 1,
                1 if success else 0, 0 if success else 1
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_overview_stats(self) -> Dict:
        """Get overview statistics"""
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            # Total posts
            c.execute('SELECT COUNT(*) FROM posts')
            total_posts = c.fetchone()[0]
            
            # Posts by status
            c.execute('SELECT status, COUNT(*) FROM posts GROUP BY status')
            status_counts = dict(c.fetchall())
            
            # Success rate
            c.execute('SELECT COUNT(*) FROM post_analytics WHERE success = 1')
            successful = c.fetchone()[0]
            c.execute('SELECT COUNT(*) FROM post_analytics')
            total_group_posts = c.fetchone()[0]
            success_rate = (successful / total_group_posts * 100) if total_group_posts > 0 else 0
            
            # Total groups
            c.execute('SELECT COUNT(DISTINCT group_username) FROM group_performance')
            total_groups = c.fetchone()[0]
            
            # Today's stats
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute('SELECT * FROM daily_stats WHERE date = ?', (today,))
            today_row = c.fetchone()
            today_stats = dict(today_row) if today_row else {'total_posts': 0, 'successful_posts': 0}
            
            return {
                'total_posts': total_posts,
                'status_counts': status_counts,
                'success_rate': round(success_rate, 1),
                'total_groups': total_groups,
                'today': today_stats,
            }
        finally:
            conn.close()
    
    def get_daily_stats(self, days: int = 30) -> List[Dict]:
        """Get daily statistics for the last N days"""
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            c.execute('''
                SELECT date, total_posts, successful_posts, failed_posts, groups_posted
                FROM daily_stats
                WHERE date >= ?
                ORDER BY date
            ''', (start_date,))
            
            rows = c.fetchall()
            
            # Fill in missing dates
            result = []
            current = datetime.now() - timedelta(days=days)
            stats_by_date = {row['date']: dict(row) for row in rows}
            
            for _ in range(days + 1):
                date_str = current.strftime('%Y-%m-%d')
                if date_str in stats_by_date:
                    result.append(stats_by_date[date_str])
                else:
                    result.append({
                        'date': date_str,
                        'total_posts': 0,
                        'successful_posts': 0,
                        'failed_posts': 0,
                        'groups_posted': 0,
                    })
                current += timedelta(days=1)
            
            return result
        finally:
            conn.close()
    
    def get_hourly_distribution(self, days: int = 7) -> List[Dict]:
        """Get posting distribution by hour of day"""
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            c.execute('''
                SELECT strftime('%H', posted_at) as hour, COUNT(*) as count, SUM(success) as success
                FROM post_analytics
                WHERE posted_at >= ?
                GROUP BY hour
                ORDER BY hour
            ''', (start_date,))
            
            rows = c.fetchall()
            
            # Fill in all hours
            hourly = {str(h).zfill(2): {'hour': h, 'count': 0, 'success': 0} for h in range(24)}
            for row in rows:
                hour = row['hour']
                hourly[hour] = {'hour': int(hour), 'count': row['count'], 'success': row['success'] or 0}
            
            return list(hourly.values())
        finally:
            conn.close()
    
    def get_group_performance(self, limit: int = 20) -> List[Dict]:
        """Get top performing groups"""
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            c.execute('''
                SELECT group_username, group_name, total_posts, successful_posts, failed_posts,
                       last_post_at, avg_response_time_ms,
                       CAST(successful_posts AS FLOAT) / NULLIF(total_posts, 0) * 100 as success_rate
                FROM group_performance
                ORDER BY total_posts DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in c.fetchall()]
        finally:
            conn.close()
    
    def get_best_posting_times(self) -> Dict:
        """Analyze best times to post based on success rates"""
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            # By hour
            c.execute('''
                SELECT strftime('%H', posted_at) as hour,
                       COUNT(*) as total,
                       SUM(success) as success,
                       CAST(SUM(success) AS FLOAT) / COUNT(*) * 100 as rate
                FROM post_analytics
                WHERE posted_at >= date('now', '-30 days')
                GROUP BY hour
                HAVING total >= 5
                ORDER BY rate DESC
            ''')
            
            by_hour = [dict(row) for row in c.fetchall()]
            
            # By day of week
            c.execute('''
                SELECT strftime('%w', posted_at) as dow,
                       COUNT(*) as total,
                       SUM(success) as success,
                       CAST(SUM(success) AS FLOAT) / COUNT(*) * 100 as rate
                FROM post_analytics
                WHERE posted_at >= date('now', '-30 days')
                GROUP BY dow
                HAVING total >= 5
                ORDER BY rate DESC
            ''')
            
            days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            by_day = []
            for row in c.fetchall():
                r = dict(row)
                r['day_name'] = days[int(r['dow'])]
                by_day.append(r)
            
            best_hour = by_hour[0] if by_hour else None
            best_day = by_day[0] if by_day else None
            
            return {
                'by_hour': by_hour[:5],  # Top 5 hours
                'by_day': by_day,
                'recommendation': {
                    'best_hour': int(best_hour['hour']) if best_hour else None,
                    'best_day': best_day['day_name'] if best_day else None,
                }
            }
        finally:
            conn.close()
    
    def export_to_csv(self, days: int = 30) -> str:
        """Export analytics to CSV format"""
        import csv
        import io
        
        conn = get_db_connection()
        c = conn.cursor()
        
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            c.execute('''
                SELECT pa.*, p.content
                FROM post_analytics pa
                JOIN posts p ON pa.post_id = p.id
                WHERE pa.posted_at >= ?
                ORDER BY pa.posted_at DESC
            ''', (start_date,))
            
            rows = c.fetchall()
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID', 'Post ID', 'Group', 'Posted At', 'Success', 'Error', 'Content'])
            
            for row in rows:
                writer.writerow([
                    row['id'],
                    row['post_id'],
                    row['group_name'],
                    row['posted_at'],
                    'Yes' if row['success'] else 'No',
                    row['error_message'] or '',
                    row['content'][:100] + '...' if len(row['content']) > 100 else row['content']
                ])
            
            return output.getvalue()
        finally:
            conn.close()
    
    def generate_report(self, days: int = 30) -> Dict:
        """Generate a comprehensive analytics report"""
        overview = self.get_overview_stats()
        daily = self.get_daily_stats(days)
        hourly = self.get_hourly_distribution(days)
        groups = self.get_group_performance(10)
        best_times = self.get_best_posting_times()
        
        # Calculate trends
        if len(daily) >= 7:
            recent_week = sum(d['total_posts'] for d in daily[-7:])
            previous_week = sum(d['total_posts'] for d in daily[-14:-7]) if len(daily) >= 14 else 0
            trend = ((recent_week - previous_week) / previous_week * 100) if previous_week > 0 else 0
        else:
            trend = 0
        
        return {
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'overview': overview,
            'daily_stats': daily,
            'hourly_distribution': hourly,
            'top_groups': groups,
            'best_times': best_times,
            'trend_percent': round(trend, 1),
        }


# Global instance
analytics = AnalyticsManager()
