"""
Scheduling system for Facebook auto-poster
Allows posting at specific times or recurring schedules
"""
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict
from configs import PROJECT_ROOT
from utils import parse_schedule, should_post_now
import os


class PostScheduler:
    def __init__(self, schedule_file=None):
        self.schedule_file = schedule_file or f"{PROJECT_ROOT}/schedule.json"
        self.schedules = self.load_schedules()
    
    def load_schedules(self) -> List[Dict]:
        """Load scheduled posts from JSON file"""
        try:
            if os.path.exists(self.schedule_file):
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"[-] Error loading schedules: {e}")
            return []
    
    def save_schedules(self) -> bool:
        """Save schedules to JSON file"""
        try:
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedules, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[-] Error saving schedules: {e}")
            return False
    
    def add_schedule(self, content: str, groups: List[str], schedule_time: str, 
                    image_path: str = None, recurring: bool = False, 
                    interval_hours: int = 24) -> Dict:
        """
        Add a new scheduled post
        
        Args:
            content: Post content
            groups: List of group usernames
            schedule_time: When to post (format: "14:30", "2025-12-24 14:30", "30m")
            image_path: Optional image to post
            recurring: Whether to repeat this post
            interval_hours: Hours between recurring posts
        """
        scheduled_dt = parse_schedule(schedule_time)
        if not scheduled_dt:
            return {'success': False, 'error': 'Invalid schedule format'}
        
        schedule = {
            'id': int(time.time() * 1000),  # Unique ID
            'content': content,
            'groups': groups,
            'schedule_time': scheduled_dt.isoformat(),
            'image_path': image_path,
            'recurring': recurring,
            'interval_hours': interval_hours,
            'status': 'pending',
            'created_at': datetime.now().isoformat()
        }
        
        self.schedules.append(schedule)
        self.save_schedules()
        
        return {'success': True, 'schedule': schedule}
    
    def get_pending_schedules(self) -> List[Dict]:
        """Get schedules that are ready to be posted"""
        pending = []
        for schedule in self.schedules:
            if schedule['status'] == 'pending':
                schedule_dt = datetime.fromisoformat(schedule['schedule_time'])
                if should_post_now(schedule_dt):
                    pending.append(schedule)
        return pending
    
    def mark_completed(self, schedule_id: int) -> bool:
        """Mark a schedule as completed"""
        for schedule in self.schedules:
            if schedule['id'] == schedule_id:
                if schedule['recurring']:
                    # Reschedule for next interval
                    old_time = datetime.fromisoformat(schedule['schedule_time'])
                    new_time = old_time + timedelta(hours=schedule['interval_hours'])
                    schedule['schedule_time'] = new_time.isoformat()
                    schedule['last_posted'] = datetime.now().isoformat()
                else:
                    schedule['status'] = 'completed'
                    schedule['completed_at'] = datetime.now().isoformat()
                
                self.save_schedules()
                return True
        return False
    
    def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule"""
        original_len = len(self.schedules)
        self.schedules = [s for s in self.schedules if s['id'] != schedule_id]
        if len(self.schedules) < original_len:
            self.save_schedules()
            return True
        return False
    
    def get_all_schedules(self) -> List[Dict]:
        """Get all schedules"""
        return self.schedules
    
    def get_next_scheduled_time(self) -> str:
        """Get the next scheduled post time"""
        pending = [s for s in self.schedules if s['status'] == 'pending']
        if not pending:
            return "No scheduled posts"
        
        next_schedule = min(pending, key=lambda x: x['schedule_time'])
        schedule_dt = datetime.fromisoformat(next_schedule['schedule_time'])
        
        time_diff = schedule_dt - datetime.now()
        if time_diff.total_seconds() < 0:
            return "Now (overdue)"
        
        hours = int(time_diff.total_seconds() // 3600)
        minutes = int((time_diff.total_seconds() % 3600) // 60)
        
        if hours > 24:
            days = hours // 24
            return f"in {days} days"
        elif hours > 0:
            return f"in {hours}h {minutes}m"
        else:
            return f"in {minutes} minutes"


def run_scheduler_loop(poster_class, check_interval: int = 60):
    """
    Continuous scheduler loop - checks every minute for pending posts
    
    Args:
        poster_class: FacebookGroupSpam class
        check_interval: Seconds between checks (default 60)
    """
    scheduler = PostScheduler()
    print("[*] Scheduler started. Checking for pending posts...")
    print(f"[*] Next post: {scheduler.get_next_scheduled_time()}")
    
    while True:
        try:
            pending = scheduler.get_pending_schedules()
            
            if pending:
                print(f"\n[!] Found {len(pending)} post(s) ready to publish!")
                
                for schedule in pending:
                    print(f"\n[*] Executing scheduled post (ID: {schedule['id']})")
                    
                    # Create poster instance
                    poster = poster_class(
                        post_content=schedule['content'],
                        image_path=schedule.get('image_path')
                    )
                    
                    # Get groups
                    from configs import get_sources_list
                    all_groups = get_sources_list()
                    target_groups = [g for g in all_groups if g['username'] in schedule['groups']]
                    
                    # Start browser and post
                    poster.start_browser()
                    poster.load_cookie()
                    results = poster.post_to_groups(target_groups)
                    poster.close_browser()
                    
                    # Mark as completed
                    scheduler.mark_completed(schedule['id'])
                    
                    success_count = sum(1 for r in results if r['success'])
                    print(f"\n[+] Posted to {success_count}/{len(results)} groups")
            
            # Wait before next check
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            print("\n[*] Scheduler stopped by user")
            break
        except Exception as e:
            print(f"[-] Scheduler error: {e}")
            time.sleep(check_interval)
