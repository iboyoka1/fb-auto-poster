"""
Centralized logging configuration with rotation support
"""
import logging
import logging.handlers
import os
import sys
from datetime import datetime

# Import config values
try:
    from config import PROJECT_ROOT, LOG_LEVEL, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT
except ImportError:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    LOG_LEVEL = "INFO"
    LOG_FILE = "logs/app.log"
    LOG_MAX_BYTES = 10485760
    LOG_BACKUP_COUNT = 5


class ColoredFormatter(logging.Formatter):
    """Colored console output formatter"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class StructuredFormatter(logging.Formatter):
    """JSON-like structured logging for file output"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ('name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'pathname', 'process', 'processName', 'relativeCreated',
                          'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                          'message', 'taskName'):
                log_data[key] = value
        
        import json
        return json.dumps(log_data)


def setup_logging(name: str = "fb_auto_poster") -> logging.Logger:
    """
    Configure and return the application logger
    
    Features:
    - Console output with colors
    - File output with rotation
    - Structured JSON logs for parsing
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    console_handler.setFormatter(ColoredFormatter(console_format, datefmt="%H:%M:%S"))
    logger.addHandler(console_handler)
    
    # File handler with rotation
    log_path = os.path.join(PROJECT_ROOT, LOG_FILE)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(StructuredFormatter())
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """Get a child logger for a specific module"""
    base_logger = setup_logging()
    if name:
        return base_logger.getChild(name)
    return base_logger


# Create default logger instance
logger = setup_logging()
