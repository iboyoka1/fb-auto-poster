"""
Session monitoring and backup utilities
"""
import os
import json
import shutil
import threading
import time
import requests
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

try:
    from config import (
        PROJECT_ROOT,
        SESSION_CHECK_INTERVAL_MINUTES,
        SESSION_ALERT_WEBHOOK,
        ENABLE_AUTO_BACKUP,
        BACKUP_INTERVAL_HOURS,
        BACKUP_MAX_FILES,
    )
except ImportError:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    SESSION_CHECK_INTERVAL_MINUTES = 30
    SESSION_ALERT_WEBHOOK = None
    ENABLE_AUTO_BACKUP = True
    BACKUP_INTERVAL_HOURS = 24
    BACKUP_MAX_FILES = 7

try:
    from logger import get_logger
    logger = get_logger("session_monitor")
except ImportError:
    import logging
    logger = logging.getLogger("session_monitor")


class SessionMonitor:
    """
    Background session monitoring with alerts
    """
    
    def __init__(self, validate_func: Optional[Callable[[], bool]] = None):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._validate_func = validate_func
        self._last_check: Optional[datetime] = None
        self._last_status: Optional[bool] = None
        self._alert_sent = False
    
    def start(self):
        """Start the monitoring thread"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"Session monitor started (check every {SESSION_CHECK_INTERVAL_MINUTES} minutes)")
    
    def stop(self):
        """Stop the monitoring thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                self._check_session()
            except Exception as e:
                logger.error(f"Session check error: {e}")
            
            # Sleep in small increments for faster shutdown
            for _ in range(SESSION_CHECK_INTERVAL_MINUTES * 60):
                if not self._running:
                    break
                time.sleep(1)
    
    def _check_session(self):
        """Check session validity and send alerts if needed"""
        self._last_check = datetime.now()
        
        # Check if session file exists
        session_file = os.path.join(PROJECT_ROOT, "sessions", "facebook-cookies.json")
        if not os.path.exists(session_file):
            self._handle_invalid_session("No session file found")
            return
        
        # Check session age
        file_age = time.time() - os.path.getmtime(session_file)
        age_days = file_age / 86400
        
        if age_days > 7:
            logger.warning(f"Session file is {age_days:.1f} days old")
        
        # Use custom validation if provided
        if self._validate_func:
            try:
                is_valid = self._validate_func()
                if is_valid:
                    self._last_status = True
                    self._alert_sent = False
                    logger.debug("Session validation passed")
                else:
                    self._handle_invalid_session("Session validation failed")
            except Exception as e:
                self._handle_invalid_session(f"Validation error: {e}")
        else:
            # Basic file-based check only
            self._last_status = True
            logger.debug("Session file exists (no deep validation)")
    
    def _handle_invalid_session(self, reason: str):
        """Handle invalid session with alerts"""
        self._last_status = False
        logger.warning(f"Session invalid: {reason}")
        
        if not self._alert_sent:
            self._send_alert(reason)
            self._alert_sent = True
    
    def _send_alert(self, reason: str):
        """Send alert via webhook"""
        if not SESSION_ALERT_WEBHOOK:
            return
        
        try:
            payload = {
                "text": f"⚠️ FB Auto Poster Session Alert\n\nReason: {reason}\nTime: {datetime.now().isoformat()}\n\nPlease login again to restore session.",
                "username": "FB Auto Poster",
            }
            
            # Support both Slack and Discord webhooks
            if "discord" in SESSION_ALERT_WEBHOOK.lower():
                payload = {"content": payload["text"]}
            
            requests.post(SESSION_ALERT_WEBHOOK, json=payload, timeout=10)
            logger.info("Session alert sent successfully")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def get_status(self) -> dict:
        """Get current session status"""
        return {
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "is_valid": self._last_status,
            "alert_sent": self._alert_sent,
            "monitoring": self._running,
        }


class BackupManager:
    """
    Automatic backup of critical data files
    """
    
    FILES_TO_BACKUP = [
        "posts.db",
        "schedule.json",
        "groups.json",
        "sessions/facebook-cookies.json",
    ]
    
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._backup_dir = os.path.join(PROJECT_ROOT, "backups")
        self._last_backup: Optional[datetime] = None
    
    def start(self):
        """Start the backup thread"""
        if not ENABLE_AUTO_BACKUP:
            logger.info("Auto backup disabled")
            return
        
        if self._running:
            return
        
        os.makedirs(self._backup_dir, exist_ok=True)
        
        self._running = True
        self._thread = threading.Thread(target=self._backup_loop, daemon=True)
        self._thread.start()
        logger.info(f"Backup manager started (every {BACKUP_INTERVAL_HOURS} hours)")
    
    def stop(self):
        """Stop the backup thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _backup_loop(self):
        """Main backup loop"""
        # Initial backup
        self.create_backup()
        
        while self._running:
            # Sleep in small increments
            for _ in range(BACKUP_INTERVAL_HOURS * 3600):
                if not self._running:
                    break
                time.sleep(1)
            
            if self._running:
                self.create_backup()
    
    def create_backup(self, tag: str = None) -> Optional[str]:
        """
        Create a backup of all critical files
        
        Args:
            tag: Optional tag for the backup (default: timestamp)
            
        Returns:
            Path to backup directory or None on failure
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{tag or timestamp}"
        backup_path = os.path.join(self._backup_dir, backup_name)
        
        try:
            os.makedirs(backup_path, exist_ok=True)
            
            files_backed_up = 0
            for file_rel in self.FILES_TO_BACKUP:
                src = os.path.join(PROJECT_ROOT, file_rel)
                if os.path.exists(src):
                    dst_dir = os.path.join(backup_path, os.path.dirname(file_rel))
                    os.makedirs(dst_dir, exist_ok=True)
                    dst = os.path.join(backup_path, file_rel)
                    shutil.copy2(src, dst)
                    files_backed_up += 1
            
            self._last_backup = datetime.now()
            logger.info(f"Backup created: {backup_name} ({files_backed_up} files)")
            
            # Cleanup old backups
            self._cleanup_old_backups()
            
            return backup_path
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Remove backups exceeding the max count"""
        try:
            backups = sorted(Path(self._backup_dir).iterdir(), key=lambda p: p.stat().st_mtime)
            
            while len(backups) > BACKUP_MAX_FILES:
                oldest = backups.pop(0)
                shutil.rmtree(oldest)
                logger.debug(f"Removed old backup: {oldest.name}")
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    def restore_backup(self, backup_name: str) -> bool:
        """
        Restore from a backup
        
        Args:
            backup_name: Name of the backup directory
            
        Returns:
            True if successful
        """
        backup_path = os.path.join(self._backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            logger.error(f"Backup not found: {backup_name}")
            return False
        
        try:
            for file_rel in self.FILES_TO_BACKUP:
                src = os.path.join(backup_path, file_rel)
                if os.path.exists(src):
                    dst = os.path.join(PROJECT_ROOT, file_rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
            
            logger.info(f"Restored from backup: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def list_backups(self) -> list:
        """List all available backups"""
        if not os.path.exists(self._backup_dir):
            return []
        
        backups = []
        for entry in sorted(Path(self._backup_dir).iterdir(), reverse=True):
            if entry.is_dir() and entry.name.startswith("backup_"):
                stat = entry.stat()
                backups.append({
                    "name": entry.name,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_mb": sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()) / 1048576,
                })
        
        return backups
    
    def get_status(self) -> dict:
        """Get backup status"""
        return {
            "enabled": ENABLE_AUTO_BACKUP,
            "running": self._running,
            "last_backup": self._last_backup.isoformat() if self._last_backup else None,
            "backup_count": len(self.list_backups()),
            "interval_hours": BACKUP_INTERVAL_HOURS,
        }


# Global instances
session_monitor = SessionMonitor()
backup_manager = BackupManager()
