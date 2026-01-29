"""
Sentry error monitoring integration
"""
import os
import functools
from typing import Optional, Callable, Any

# Lazy import sentry_sdk to avoid errors if not installed
_sentry_initialized = False

def init_sentry(
    dsn: Optional[str] = None,
    environment: str = 'development',
    release: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
    debug: bool = False
) -> bool:
    """
    Initialize Sentry error monitoring.
    
    Args:
        dsn: Sentry DSN (from environment or parameter)
        environment: deployment environment
        release: version string
        traces_sample_rate: performance monitoring sample rate
        profiles_sample_rate: profiling sample rate
        debug: enable debug logging
    
    Returns:
        True if initialized successfully
    """
    global _sentry_initialized
    
    dsn = dsn or os.getenv('SENTRY_DSN', '')
    
    if not dsn:
        print("[Sentry] No DSN configured, error monitoring disabled")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.threading import ThreadingIntegration
        
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release or os.getenv('APP_VERSION', 'unknown'),
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            integrations=[
                FlaskIntegration(),
                ThreadingIntegration(propagate_hub=True),
            ],
            debug=debug,
            # Filter out sensitive data
            before_send=_filter_sensitive_data,
            # Don't send PII
            send_default_pii=False,
        )
        
        _sentry_initialized = True
        print(f"[Sentry] Initialized for environment: {environment}")
        return True
        
    except ImportError:
        print("[Sentry] sentry-sdk not installed. Run: pip install sentry-sdk[flask]")
        return False
    except Exception as e:
        print(f"[Sentry] Failed to initialize: {e}")
        return False


def _filter_sensitive_data(event: dict, hint: dict) -> dict:
    """Filter out sensitive data before sending to Sentry"""
    
    # Remove sensitive headers
    if 'request' in event:
        if 'headers' in event['request']:
            headers = event['request']['headers']
            sensitive_headers = ['cookie', 'authorization', 'x-csrf-token']
            for header in sensitive_headers:
                if header in headers:
                    headers[header] = '[Filtered]'
    
    # Remove sensitive data from extra context
    if 'extra' in event:
        sensitive_keys = ['password', 'token', 'secret', 'cookie', 'credentials']
        for key in list(event['extra'].keys()):
            if any(s in key.lower() for s in sensitive_keys):
                event['extra'][key] = '[Filtered]'
    
    return event


def capture_exception(error: Exception, context: Optional[dict] = None) -> Optional[str]:
    """
    Capture an exception and send to Sentry.
    
    Args:
        error: Exception to capture
        context: Additional context to include
    
    Returns:
        Event ID if captured, None otherwise
    """
    if not _sentry_initialized:
        return None
    
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            
            return sentry_sdk.capture_exception(error)
    except:
        return None


def capture_message(message: str, level: str = 'info', context: Optional[dict] = None) -> Optional[str]:
    """
    Capture a message and send to Sentry.
    
    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
        context: Additional context
    
    Returns:
        Event ID if captured, None otherwise
    """
    if not _sentry_initialized:
        return None
    
    try:
        import sentry_sdk
        
        with sentry_sdk.push_scope() as scope:
            scope.level = level
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            
            return sentry_sdk.capture_message(message)
    except:
        return None


def set_user(user_id: str, email: Optional[str] = None, username: Optional[str] = None):
    """Set the current user context for Sentry"""
    if not _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.set_user({
            'id': user_id,
            'email': email,
            'username': username
        })
    except:
        pass


def add_breadcrumb(message: str, category: str = 'default', level: str = 'info', data: Optional[dict] = None):
    """Add a breadcrumb for debugging"""
    if not _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )
    except:
        pass


def set_context(name: str, data: dict):
    """Set additional context"""
    if not _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.set_context(name, data)
    except:
        pass


def set_tag(key: str, value: str):
    """Set a tag for filtering"""
    if not _sentry_initialized:
        return
    
    try:
        import sentry_sdk
        sentry_sdk.set_tag(key, value)
    except:
        pass


def monitored(operation_name: Optional[str] = None):
    """
    Decorator to monitor a function with Sentry.
    
    Captures exceptions and adds performance tracing.
    
    Usage:
        @monitored('post_to_group')
        def post_to_group(group_id, content):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            op_name = operation_name or func.__name__
            
            if not _sentry_initialized:
                return func(*args, **kwargs)
            
            try:
                import sentry_sdk
                
                with sentry_sdk.start_transaction(op='function', name=op_name) as transaction:
                    try:
                        result = func(*args, **kwargs)
                        transaction.set_status('ok')
                        return result
                    except Exception as e:
                        transaction.set_status('internal_error')
                        sentry_sdk.capture_exception(e)
                        raise
                        
            except ImportError:
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


class SentryContext:
    """Context manager for Sentry scope"""
    
    def __init__(self, **tags):
        self.tags = tags
        self._scope = None
    
    def __enter__(self):
        if not _sentry_initialized:
            return self
        
        try:
            import sentry_sdk
            self._scope = sentry_sdk.push_scope()
            scope = self._scope.__enter__()
            
            for key, value in self.tags.items():
                scope.set_tag(key, value)
            
            return scope
        except:
            return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._scope:
            if exc_val:
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(exc_val)
                except:
                    pass
            
            self._scope.__exit__(exc_type, exc_val, exc_tb)
        
        return False


# Performance monitoring helpers
def start_transaction(name: str, op: str = 'task'):
    """Start a performance transaction"""
    if not _sentry_initialized:
        return None
    
    try:
        import sentry_sdk
        return sentry_sdk.start_transaction(name=name, op=op)
    except:
        return None


def start_span(description: str, op: str = 'subtask'):
    """Start a span within a transaction"""
    if not _sentry_initialized:
        return None
    
    try:
        import sentry_sdk
        return sentry_sdk.start_span(description=description, op=op)
    except:
        return None


# Health check
def is_initialized() -> bool:
    """Check if Sentry is initialized"""
    return _sentry_initialized


def get_last_event_id() -> Optional[str]:
    """Get the last event ID"""
    if not _sentry_initialized:
        return None
    
    try:
        import sentry_sdk
        return sentry_sdk.last_event_id()
    except:
        return None
