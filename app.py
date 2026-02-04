from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, Response
from datetime import datetime
import json
import os
import sys
from configs import PROJECT_ROOT, DASHBOARD_USERNAME, DASHBOARD_PASSWORD
from scheduler import PostScheduler
from utils import spin_text, load_groups_from_csv
import sqlite3
from functools import wraps
from typing import Dict, List
import time

# Import new modules
try:
    from config import (
        SERVER_PORT, SERVER_HOST, DEBUG_MODE, 
        ENABLE_MULTI_ACCOUNT, ENABLE_MEDIA_LIBRARY, ENABLE_CONTENT_TEMPLATES,
        SENTRY_DSN, get_config_summary
    )
except ImportError:
    SERVER_PORT = 5000
    SERVER_HOST = '0.0.0.0'
    DEBUG_MODE = False
    ENABLE_MULTI_ACCOUNT = False
    ENABLE_MEDIA_LIBRARY = False
    ENABLE_CONTENT_TEMPLATES = False
    SENTRY_DSN = ''
    get_config_summary = lambda: {}

try:
    from logger import setup_logging, get_logger
    setup_logging()
    logger = get_logger('app')
except ImportError:
    import logging
    logger = logging.getLogger('app')

try:
    from rate_limiter import RateLimiter, get_smart_delay
    rate_limiter = RateLimiter()
except ImportError:
    rate_limiter = None
    get_smart_delay = lambda *a, **k: 5

try:
    from analytics import AnalyticsManager
    analytics_mgr = AnalyticsManager()
except ImportError:
    analytics_mgr = None

try:
    from content_manager import ContentTemplateManager, DraftManager
    template_mgr = ContentTemplateManager()
    draft_mgr = DraftManager()
except ImportError:
    template_mgr = None
    draft_mgr = None

try:
    from multi_account import AccountManager
    account_mgr = AccountManager() if ENABLE_MULTI_ACCOUNT else None
except ImportError:
    account_mgr = None

# Security modules
try:
    from security import (
        password_manager, token_manager, credential_encryption, 
        rate_limiter as security_rate_limiter
    )
except ImportError:
    password_manager = None
    token_manager = None
    credential_encryption = None
    security_rate_limiter = None

try:
    from setup_wizard import SetupWizard
except ImportError:
    SetupWizard = None

try:
    from media_library import MediaLibrary
    media_lib = MediaLibrary() if ENABLE_MEDIA_LIBRARY else None
except ImportError:
    media_lib = None

try:
    from session_monitor import SessionMonitor, BackupManager
    backup_mgr = BackupManager()
except ImportError:
    backup_mgr = None

try:
    from api_docs import api_docs
except ImportError:
    api_docs = None

# Initialize Sentry error monitoring
try:
    from error_monitoring import init_sentry, capture_exception, monitored
    if SENTRY_DSN:
        init_sentry(dsn=SENTRY_DSN)
except ImportError:
    capture_exception = lambda e, c=None: None
    monitored = lambda n=None: lambda f: f

# Get the directory where app.py is located
APP_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
    static_folder=os.path.join(APP_DIR, 'static'),
    static_url_path='/static',
    template_folder=os.path.join(APP_DIR, 'templates'))

# Use a fixed secret key (or from environment variable) to keep sessions valid across restarts
app.secret_key = os.environ.get('SECRET_KEY', 'fb-auto-poster-secret-key-2024-stable')

# Debug: Print paths at startup
print(f"[STARTUP] APP_DIR: {APP_DIR}")
print(f"[STARTUP] Static folder: {os.path.join(APP_DIR, 'static')}")
print(f"[STARTUP] Static folder exists: {os.path.exists(os.path.join(APP_DIR, 'static'))}")
print(f"[STARTUP] Template folder: {os.path.join(APP_DIR, 'templates')}")
print(f"[STARTUP] Template folder exists: {os.path.exists(os.path.join(APP_DIR, 'templates'))}")

# Configure session for smooth persistence
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 7 * 24 * 60 * 60  # 7 days
app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Refresh on each request
app.config['SESSION_COOKIE_SECURE'] = False  # Allow HTTP for local dev
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Secure cookies
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

# Initialize Flask-Session for persistent sessions
try:
    from flask_session import Session
    Session(app)
    print("[SESSION] Flask-Session initialized successfully")
except ImportError:
    print("[SESSION] Flask-Session not installed, using default Flask sessions")
except Exception as e:
    print(f"[SESSION] Error initializing Flask-Session: {e}")

# Register API docs blueprint
if api_docs:
    app.register_blueprint(api_docs)

DATABASE = f"{PROJECT_ROOT}/posts.db"
ACTIVE_POSTS: Dict[int, Dict] = {}

# Ensure required directories exist for local usage
try:
    os.makedirs(f"{PROJECT_ROOT}/sessions", exist_ok=True)
    os.makedirs(f"{PROJECT_ROOT}/uploads", exist_ok=True)
except Exception:
    pass

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            groups_posted TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
    conn.commit()
    conn.close()

# Initialize database on module load (important for gunicorn/production)
init_db()
print("[DATABASE] Database initialized")

@app.context_processor
def inject_csrf():
    token = session.get('csrf_token')
    if not token:
        token = os.urandom(16).hex()
        session['csrf_token'] = token
    return {'csrf_token': token}

@app.before_request
def enforce_csrf():
    # Enforce CSRF for state-changing methods
    if request.method in ("POST", "PUT", "DELETE"):
        # Exempt API endpoints, login, and static files from CSRF
        if request.endpoint and (request.endpoint.startswith('static') or request.path.startswith('/api/') or request.path == '/login'):
            return
        token_header = request.headers.get('X-CSRF-Token')
        expected = session.get('csrf_token')
        if not expected or not token_header or token_header != expected:
            return jsonify({'success': False, 'error': 'CSRF token missing or invalid'}), 403

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for Render deployment"""
    return jsonify({'status': 'ok', 'healthy': True}), 200

@app.route('/api/upload-cookies', methods=['POST'])
@login_required
def upload_cookies():
    """Upload Facebook cookies from local machine to server (for cloud deployment)"""
    try:
        data = request.get_json(silent=True) or {}
        cookies = data.get('cookies', [])
        
        if not cookies:
            return jsonify({'success': False, 'error': 'No cookies provided'}), 400
        
        # Validate cookies have required fields
        cookie_names = {c.get('name') for c in cookies}
        if 'c_user' not in cookie_names or 'xs' not in cookie_names:
            return jsonify({'success': False, 'error': 'Invalid cookies - missing c_user or xs'}), 400
        
        # Save cookies to file
        cookie_path = os.path.join(PROJECT_ROOT, 'sessions', 'facebook-cookies.json')
        os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
        
        with open(cookie_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2)
        
        # Update session
        c_user = next((c.get('value') for c in cookies if c.get('name') == 'c_user'), None)
        session['facebook_connected'] = True
        session['facebook_authenticated'] = True
        session['facebook_email'] = f"User {c_user}"
        session.modified = True
        
        logger.info(f"[UPLOAD COOKIES] Successfully uploaded cookies for user {c_user}")
        return jsonify({
            'success': True, 
            'message': 'Cookies uploaded successfully',
            'user_id': c_user
        }), 200
        
    except Exception as e:
        logger.error(f"[UPLOAD COOKIES] Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-groups', methods=['POST'])
@login_required
def upload_groups():
    """Upload groups.json from local machine to server (for cloud deployment)"""
    try:
        data = request.get_json(silent=True) or {}
        groups = data.get('groups', [])
        
        if not groups:
            return jsonify({'success': False, 'error': 'No groups provided'}), 400
        
        # Normalize and validate groups - handle different formats
        normalized_groups = []
        for g in groups:
            # Handle different input formats
            if isinstance(g, str):
                # Just a group ID string
                normalized_groups.append({
                    'name': g,
                    'username': g,
                    'status': 'member'
                })
            elif isinstance(g, dict):
                # Try to extract username from various fields
                username = (
                    g.get('username') or 
                    g.get('id') or 
                    g.get('group_id') or 
                    g.get('groupId') or
                    g.get('url', '').split('/groups/')[-1].strip('/').split('?')[0] or
                    None
                )
                
                if not username:
                    logger.warning(f"[UPLOAD GROUPS] Skipping group with no identifier: {g}")
                    continue
                
                name = g.get('name') or g.get('title') or g.get('groupName') or username
                
                normalized_groups.append({
                    'name': name,
                    'username': username,
                    'status': g.get('status', 'member')
                })
            else:
                logger.warning(f"[UPLOAD GROUPS] Skipping invalid group format: {g}")
                continue
        
        if not normalized_groups:
            return jsonify({'success': False, 'error': 'No valid groups found. Groups need an id, username, or url field.'}), 400
        
        # Save groups to file
        groups_path = os.path.join(PROJECT_ROOT, 'groups.json')
        with open(groups_path, 'w', encoding='utf-8') as f:
            json.dump(normalized_groups, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[UPLOAD GROUPS] Successfully uploaded {len(normalized_groups)} groups")
        return jsonify({
            'success': True, 
            'message': f'Uploaded {len(normalized_groups)} groups successfully',
            'count': len(normalized_groups)
        }), 200
        
    except Exception as e:
        logger.error(f"[UPLOAD GROUPS] Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/facebook-status', methods=['GET'])
def facebook_status():
    """Check if user is connected to Facebook - checks both session and cookie file"""
    try:
        # First check Flask session
        fb_connected = session.get('facebook_connected', False)
        fb_email = session.get('facebook_email', '')
        fb_authenticated = session.get('facebook_authenticated', False)
        
        # Also check if we have valid cookies saved (in case session was lost)
        session_file = os.path.join(PROJECT_ROOT, 'sessions', 'facebook-cookies.json')
        logger.info(f"Checking cookie file: {session_file}, exists: {os.path.exists(session_file)}")
        
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                cookie_names = {c.get('name') for c in cookies}
                logger.info(f"Found cookies: {cookie_names}")
                
                if 'c_user' in cookie_names and 'xs' in cookie_names:
                    c_user_value = next((c.get('value') for c in cookies if c.get('name') == 'c_user'), None)
                    # Cookie file is valid - update response
                    fb_connected = True
                    fb_authenticated = True
                    if not fb_email:
                        fb_email = f"User {c_user_value}"
                    logger.info(f"Facebook session valid for user: {c_user_value}")
            except Exception as e:
                logger.error(f"Error reading cookies file: {e}")
        
        return jsonify({
            'connected': fb_connected,
            'email': fb_email,
            'authenticated': fb_authenticated,
            'status': 'connected' if fb_connected else 'disconnected'
        }), 200
    except Exception as e:
        logger.error(f"Error checking Facebook status: {str(e)}")
        return jsonify({'connected': False, 'email': '', 'authenticated': False, 'status': 'error'}), 200

@app.route('/api/facebook-login', methods=['POST'])
def facebook_login():
    """Handle Facebook login with email and password - Uses Playwright for real authentication"""
    try:
        data = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''
        use_manual = data.get('manual', False)  # Option for manual login
        
        # Validation with clear error messages
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 200
        
        if not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 200
        
        if len(password) < 4:
            return jsonify({'success': False, 'error': 'Password must be at least 4 characters'}), 200
        
        # Validate email format
        if '@' not in email and not email[0].isdigit():
            return jsonify({'success': False, 'error': 'Please enter a valid email or phone number'}), 200
        
        # Save credentials to file for future use
        creds_path = os.path.join(PROJECT_ROOT, 'sessions', 'facebook-credentials.json')
        try:
            os.makedirs(os.path.dirname(creds_path), exist_ok=True)
            with open(creds_path, 'w', encoding='utf-8') as f:
                json.dump({'email': email, 'password': password}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save credentials: {e}")
        
        # Attempt real Facebook login using Playwright
        try:
            from main import FacebookGroupSpam
            cookie_path = os.path.join(PROJECT_ROOT, 'sessions', 'facebook-cookies.json')
            
            logger.info(f"[FACEBOOK LOGIN] Starting Playwright authentication for {email}")
            poster = FacebookGroupSpam(headless=True)
            poster.start_browser()
            
            success = poster.auto_login_with_credentials(email, password, timeout=45)
            
            if success:
                # Save cookies for future sessions
                poster.generate_cookie(cookie_path)
                poster.close_browser()
                
                # Store in session
                session['facebook_connected'] = True
                session['facebook_email'] = email
                session['facebook_authenticated'] = True
                session['facebook_login_time'] = datetime.now().isoformat()
                session['logged_in'] = True
                session['username'] = email.split('@')[0] if '@' in email else 'User'
                session.modified = True
                session.permanent = True
                
                logger.info(f"[FACEBOOK LOGIN SUCCESS] Real authentication successful for: {email}")
                return jsonify({
                    'success': True, 
                    'message': f'Successfully connected as {email}',
                    'email': email,
                    'connected': True
                }), 200
            else:
                poster.close_browser()
                logger.warning(f"[FACEBOOK LOGIN] Auto-login failed for {email} - may need manual login for 2FA/CAPTCHA")
                return jsonify({
                    'success': False, 
                    'error': 'Auto-login failed. Facebook may require 2FA or CAPTCHA. Try Manual Login instead.',
                    'needs_manual': True
                }), 200
                
        except ImportError as e:
            logger.error(f"[FACEBOOK LOGIN] Playwright not installed: {e}")
            return jsonify({'success': False, 'error': 'Playwright not installed. Run: pip install playwright && playwright install chromium'}), 200
        except Exception as e:
            logger.error(f"[FACEBOOK LOGIN] Playwright error: {e}")
            return jsonify({'success': False, 'error': f'Login failed: {str(e)}. Try Manual Login.', 'needs_manual': True}), 200
        
    except Exception as e:
        logger.error(f"[FACEBOOK LOGIN ERROR] {str(e)}")
        return jsonify({'success': False, 'error': 'Login failed. Please try again.'}), 200

@app.route('/api/facebook-logout', methods=['POST'])
def facebook_logout():
    """Logout from Facebook - Smooth logout flow

    This endpoint now fully clears server-side session state and removes
    any saved Facebook cookie files and account records to ensure a true logout.
    """
    try:
        email = session.get('facebook_email', 'Unknown user')

        # Clear Flask session data completely
        session_keys = ['facebook_connected', 'facebook_email', 'facebook_authenticated', 'facebook_login_time']
        for k in session_keys:
            session.pop(k, None)
        # Also clear login flags
        session.pop('logged_in', None)
        session.pop('username', None)
        session.modified = True

        # Remove saved cookie files in sessions/ (facebook-cookies.json and any account_* cookies)
        removed_files = []
        try:
            sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')
            if os.path.isdir(sessions_dir):
                for fname in os.listdir(sessions_dir):
                    if fname.endswith('-cookies.json') or fname == 'facebook-cookies.json' or 'cookie' in fname.lower():
                        path = os.path.join(sessions_dir, fname)
                        try:
                            os.remove(path)
                            removed_files.append(fname)
                        except Exception:
                            logger.warning(f"Failed to remove session file: {path}")
        except Exception as e:
            logger.warning(f"Error while cleaning sessions folder: {e}")

        # Clear accounts.json records (reset to empty list)
        try:
            accounts_path = os.path.join(PROJECT_ROOT, 'accounts.json')
            if os.path.exists(accounts_path):
                with open(accounts_path, 'w', encoding='utf-8') as f:
                    json.dump([], f)
        except Exception as e:
            logger.warning(f"Failed to clear accounts.json: {e}")

        logger.info(f"[FACEBOOK LOGOUT SUCCESS] User logged out: {email}. Removed files: {removed_files}")
        return jsonify({
            'success': True,
            'message': 'Successfully logged out from Facebook and cleared saved session data',
            'connected': False,
            'removed_files': removed_files
        }), 200

    except Exception as e:
        logger.error(f"[FACEBOOK LOGOUT ERROR] {str(e)}")
        return jsonify({'success': False, 'error': 'Logout failed. Please try again.'}), 200

@app.route('/api/facebook-check', methods=['GET'])
def facebook_check():
    """Quick check for Facebook connection status - used for smooth UX updates"""
    try:
        fb_connected = session.get('facebook_connected', False)
        fb_email = session.get('facebook_email', '')
        
        return jsonify({
            'connected': fb_connected,
            'email': fb_email,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({'connected': False, 'email': '', 'error': str(e)}), 200

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json(silent=True) or {}
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
            
            print(f"[LOGIN] Attempt: username='{username}', password length={len(password)}")
            
            # Simple credential check (no bcrypt dependency)
            expected_username = DASHBOARD_USERNAME or 'admin'
            expected_password = DASHBOARD_PASSWORD or 'password123'
            
            print(f"[LOGIN] Expected: username='{expected_username}', password length={len(expected_password)}")
            
            # Direct comparison - no hashing
            # Allow empty password for demo mode, or match exact password
            password_valid = (password == expected_password) or (not expected_password and not password)
            if username != expected_username or not password_valid:
                print(f"[LOGIN] Failed - credentials mismatch")
                return jsonify({'success': False, 'error': 'Invalid credentials. Use username: admin, password: password123'}), 200
            
            # Set session - MUST do this before returning
            session['logged_in'] = True
            session['username'] = username or 'Admin'
            session.permanent = True  # Make session persistent
            session.modified = True   # Force session save
            
            print(f"[LOGIN] Success - session created for {username}")
            print(f"[LOGIN] Session data: logged_in={session.get('logged_in')}, username={session.get('username')}")
            return jsonify({'success': True, 'redirect': url_for('dashboard')}), 200
        except Exception as e:
            print(f"[LOGIN] Error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 200
    
    # Ensure CSRF cookie is set via template context
    resp = make_response(render_template('login.html'))
    return resp

@app.route('/auth/facebook', methods=['GET'])
def facebook_auth():
    """Handle Facebook authentication"""
    # For now, just add a dummy account
    # In production, this would use OAuth2 flow
    accounts = session.get('accounts', [])
    
    # Add a demo account
    if not any(a.get('email') == 'demo@facebook.com' for a in accounts):
        accounts.append({
            'id': 'demo_fb_1',
            'name': 'Demo Facebook Account',
            'email': 'demo@facebook.com'
        })
        session['accounts'] = accounts
        session['facebook_connected'] = True
    
    return redirect(url_for('accounts'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/groups')
@login_required
def groups():
    return render_template('groups.html')

@app.route('/post')
@login_required
def post():
    return render_template('post.html')

@app.route('/history')
@login_required
def history():
    return render_template('history.html')

@app.route('/templates')
@login_required
def templates_page():
    return render_template('templates.html')

@app.route('/media')
@login_required
def media_page():
    return render_template('media.html')

@app.route('/accounts')
@login_required
def accounts():
    return render_template('accounts.html')
@login_required
def accounts_page():
    return render_template('accounts.html')

@app.route('/analytics')
@login_required
def analytics_page():
    return render_template('analytics_page.html')

# API Endpoints
@app.route('/api/groups', methods=['GET'])
@login_required
def get_groups():
    try:
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            groups = json.load(f)
        return jsonify({'success': True, 'groups': groups})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/groups', methods=['POST'])
@login_required
def add_group():
    try:
        data = request.json
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            groups = json.load(f)
        
        groups.append({
            'name': data['name'],
            'username': data['username'],
            'status': data.get('status', 'straight')
        })
        
        with open(f"{PROJECT_ROOT}/groups.json", "w", encoding='utf-8') as f:
            json.dump(groups, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Group added successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/groups/<int:index>', methods=['DELETE'])
@login_required
def delete_group(index):
    try:
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            groups = json.load(f)
        
        if 0 <= index < len(groups):
            groups.pop(index)
            with open(f"{PROJECT_ROOT}/groups.json", "w", encoding='utf-8') as f:
                json.dump(groups, f, indent=2, ensure_ascii=False)
            return jsonify({'success': True, 'message': 'Group deleted successfully'})
        return jsonify({'success': False, 'error': 'Invalid index'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/groups/<int:index>', methods=['PUT'])
@login_required
def update_group(index):
    try:
        data = request.json
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            groups = json.load(f)
        
        if 0 <= index < len(groups):
            groups[index] = {
                'name': data['name'],
                'username': data['username'],
                'status': data.get('status', 'straight')
            }
            with open(f"{PROJECT_ROOT}/groups.json", "w", encoding='utf-8') as f:
                json.dump(groups, f, indent=2, ensure_ascii=False)
            return jsonify({'success': True, 'message': 'Group updated successfully'})
        return jsonify({'success': False, 'error': 'Invalid index'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/discover-groups', methods=['POST'])
@login_required
def discover_groups_api():
    """Auto-discover Facebook groups using mobile Facebook (m.facebook.com) - server-rendered HTML"""
    import requests
    import re
    
    try:
        logger.info("=== GROUP DISCOVERY (Mobile Facebook) ===")
        
        # Load session cookies
        cookie_file = f"{PROJECT_ROOT}/sessions/facebook-cookies.json"
        if not os.path.exists(cookie_file):
            return jsonify({
                'success': False,
                'error': 'No saved session found',
                'message': 'Please upload cookies first'
            }), 400
        
        with open(cookie_file, 'r') as f:
            cookies_list = json.load(f)
        
        # Convert cookies list to requests format
        cookies = {}
        for c in cookies_list:
            cookies[c['name']] = c['value']
        
        # Check we have required cookies
        if 'c_user' not in cookies or 'xs' not in cookies:
            return jsonify({
                'success': False,
                'error': 'Invalid cookies',
                'message': 'Missing c_user or xs cookie. Please re-upload cookies.'
            }), 400
        
        user_id = cookies.get('c_user', '')
        
        # Mobile User-Agent for server-rendered HTML
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        discovered = []
        seen_ids = set()
        all_html = ""
        
        # Create a session for persistent cookies
        session = requests.Session()
        session.cookies.update(cookies)
        session.headers.update(headers)
        
        # URLs to try for discovering groups (mobile Facebook has server-rendered HTML)
        urls_to_try = [
            'https://m.facebook.com/groups/?category=membership',
            'https://m.facebook.com/groups/joins/',
            f'https://m.facebook.com/profile.php?id={user_id}&sk=groups' if user_id else None,
            f'https://m.facebook.com/{user_id}/groups' if user_id else None,
            'https://m.facebook.com/groups/',
            'https://touch.facebook.com/groups/?category=membership',
            'https://mbasic.facebook.com/groups/?category=membership',
        ]
        
        # Filter out None values
        urls_to_try = [u for u in urls_to_try if u]
        
        for url in urls_to_try:
            if len(discovered) >= 50:  # Stop if we have enough
                break
                
            try:
                logger.info(f"Trying URL: {url}")
                response = session.get(url, timeout=20, allow_redirects=True)
                
                # Check if redirected to login
                if '/login' in response.url or 'login' in response.url.lower():
                    logger.warning(f"URL {url} redirected to login")
                    continue
                
                html = response.text
                logger.info(f"Got {len(html)} bytes from {url}")
                all_html += html
                
                # Extract groups using multiple patterns
                patterns = [
                    # Mobile patterns
                    r'href="/groups/(\d+)[/\?"]',
                    r'href="[^"]*?/groups/(\d+)[/\?"]',
                    r'/groups/(\d{10,})',
                    # Named group patterns
                    r'href="/groups/([a-zA-Z][a-zA-Z0-9._]{2,49})/?["\?]',
                    # Group ID in data attributes
                    r'data-group-id="(\d+)"',
                    r'"groupID":"(\d+)"',
                    r'"group_id":"?(\d+)"?',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, html)
                    for group_id in matches:
                        if group_id and group_id not in seen_ids:
                            seen_ids.add(group_id)
                
            except requests.Timeout:
                logger.warning(f"Timeout fetching {url}")
                continue
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e}")
                continue
        
        # Filter and create group entries
        skip_keywords = {'feed', 'discover', 'joins', 'create', 'notifications', 'settings', 
                        'search', 'groups', 'profile', 'help', 'pages', 'events', 'marketplace',
                        'gaming', 'watch', 'saved', 'memories', 'friends', 'messages', 'null', 'undefined'}
        
        for group_id in seen_ids:
            if len(discovered) >= 50:  # Limit results
                break
                
            # Skip invalid
            if not group_id:
                continue
            if group_id.lower() in skip_keywords:
                continue
            if len(group_id) < 3:
                continue
            # Skip if it's a user ID (same as logged in user)
            if group_id == user_id:
                continue
            
            # Try to extract group name from collected HTML
            group_name = group_id
            name_patterns = [
                rf'/groups/{re.escape(group_id)}[^>]*?>([^<]+?)</a>',
                rf'/groups/{re.escape(group_id)}[^>]*?aria-label="([^"]+)"',
                rf'"name":"([^"]+)"[^}}]*?"id":"{group_id}"',
            ]
            
            for pattern in name_patterns:
                name_match = re.search(pattern, all_html, re.IGNORECASE)
                if name_match:
                    potential_name = name_match.group(1).strip()
                    # Clean HTML entities
                    potential_name = potential_name.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"')
                    if len(potential_name) >= 2 and len(potential_name) <= 150:
                        if potential_name.lower() not in skip_keywords:
                            group_name = potential_name
                            break
            
            discovered.append({
                'name': group_name,
                'username': group_id,
                'status': 'member',
                'type': 'group',
                'url': f"https://www.facebook.com/groups/{group_id}"
            })
        
        logger.info(f"Discovered {len(discovered)} valid groups from {len(seen_ids)} found IDs")
        
        if len(discovered) == 0:
            return jsonify({
                'success': False,
                'error': 'No groups found',
                'message': 'Could not find any groups. Make sure cookies are valid and you are a member of groups.'
            }), 404
        
        return jsonify({
            'success': True,
            'groups': discovered,
            'count': len(discovered),
            'message': f'Found {len(discovered)} groups!'
        })
    
    except requests.Timeout:
        logger.error("Request timeout")
        return jsonify({
            'success': False,
            'error': 'Timeout',
            'message': 'Request timed out. Try again.'
        }), 408
    
    except Exception as e:
        logger.error(f"Group discovery error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to discover groups'
        }), 500


# Store discovered groups temporarily for batch processing
DISCOVERY_CACHE = {}

@app.route('/api/discover-groups-batch', methods=['POST'])
@login_required
def discover_groups_batch():
    """
    Discover groups using Playwright browser - goes to Facebook and gets groups.
    Returns groups in batches of 5.
    """
    import re
    
    try:
        data = request.get_json(silent=True) or {}
        batch_num = data.get('batch', 0)
        batch_size = 5
        session_id = session.get('username', 'default')
        
        # If batch > 0, return from cache
        if batch_num > 0 and session_id in DISCOVERY_CACHE:
            cached = DISCOVERY_CACHE[session_id]
            start_idx = batch_num * batch_size
            end_idx = start_idx + batch_size
            batch_groups = cached['groups'][start_idx:end_idx]
            
            has_more = end_idx < len(cached['groups'])
            
            return jsonify({
                'success': True,
                'groups': batch_groups,
                'batch': batch_num,
                'total_found': len(cached['groups']),
                'has_more': has_more,
                'message': f'Batch {batch_num + 1}: {len(batch_groups)} groups'
            })
        
        # First call - use Playwright to discover groups
        logger.info("=== PLAYWRIGHT GROUP DISCOVERY ===")
        
        # Load session cookies
        cookie_file = f"{PROJECT_ROOT}/sessions/facebook-cookies.json"
        if not os.path.exists(cookie_file):
            return jsonify({
                'success': False,
                'error': 'No saved session found',
                'message': 'Please upload cookies first'
            }), 400
        
        with open(cookie_file, 'r') as f:
            cookies_list = json.load(f)
        
        # Validate cookies
        cookie_names = [c.get('name') for c in cookies_list]
        if 'c_user' not in cookie_names or 'xs' not in cookie_names:
            return jsonify({
                'success': False,
                'error': 'Invalid cookies',
                'message': 'Missing c_user or xs cookie.'
            }), 400
        
        user_id = next((c['value'] for c in cookies_list if c['name'] == 'c_user'), '')
        logger.info(f"User ID from cookies: {user_id}")
        
        discovered = []
        seen_ids = set()
        
        # Use Playwright to browse Facebook
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Add cookies to browser
            fb_cookies = []
            for c in cookies_list:
                cookie = {
                    'name': c['name'],
                    'value': c['value'],
                    'domain': c.get('domain', '.facebook.com'),
                    'path': c.get('path', '/'),
                }
                if c.get('expirationDate'):
                    cookie['expires'] = c['expirationDate']
                fb_cookies.append(cookie)
            
            context.add_cookies(fb_cookies)
            page = context.new_page()
            
            all_html = ""
            
            # URLs to try
            urls_to_try = [
                'https://www.facebook.com/groups/joins/',
                f'https://www.facebook.com/{user_id}/groups' if user_id else 'https://www.facebook.com/groups/feed/',
            ]
            
            for url in urls_to_try:
                if len(seen_ids) >= 100:
                    break
                try:
                    logger.info(f"Navigating to: {url}")
                    page.goto(url, timeout=30000, wait_until='domcontentloaded')
                    
                    # Check if logged in
                    if '/login' in page.url.lower():
                        logger.warning("Redirected to login - cookies may be expired")
                        continue
                    
                    # Wait for content to load
                    page.wait_for_timeout(3000)
                    
                    # Scroll to load more groups
                    for _ in range(3):
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        page.wait_for_timeout(1500)
                    
                    # Get page content
                    html = page.content()
                    all_html += html
                    logger.info(f"Got {len(html)} bytes from {url}")
                    
                    # Extract group IDs
                    patterns = [
                        r'href="[^"]*?/groups/(\d{8,})/?["\?]',
                        r'/groups/(\d{10,})',
                        r'"groupID":"(\d+)"',
                        r'"group_id":"(\d+)"',
                    ]
                    
                    for pattern in patterns:
                        for gid in re.findall(pattern, html):
                            if gid and gid not in seen_ids and gid != user_id and len(gid) >= 8:
                                seen_ids.add(gid)
                    
                    logger.info(f"Found {len(seen_ids)} unique group IDs so far")
                    
                except Exception as e:
                    logger.warning(f"Error with {url}: {e}")
                    continue
            
            browser.close()
        
        # Create group entries
        for gid in seen_ids:
            name = gid
            # Try to extract name from HTML
            name_patterns = [
                rf'/groups/{gid}[^>]*?>([^<]+)</a>',
                rf'aria-label="([^"]+)"[^>]*?/groups/{gid}',
            ]
            for np in name_patterns:
                match = re.search(np, all_html)
                if match:
                    potential = match.group(1).strip()
                    if 2 < len(potential) < 200:
                        name = potential.replace('&amp;', '&').replace('&#039;', "'")
                        break
            
            discovered.append({
                'name': name,
                'username': gid,
                'status': 'member',
                'url': f'https://www.facebook.com/groups/{gid}'
            })
        
        logger.info(f"Total discovered: {len(discovered)} groups")
        
        if not discovered:
            return jsonify({
                'success': False,
                'error': 'No groups found',
                'message': 'Could not find groups. Your cookies may have expired or you may not be a member of any groups.'
            }), 404
        
        # Cache results
        DISCOVERY_CACHE[session_id] = {
            'groups': discovered,
            'timestamp': time.time()
        }
        
        # Return first batch
        first_batch = discovered[:batch_size]
        has_more = len(discovered) > batch_size
        
        return jsonify({
            'success': True,
            'groups': first_batch,
            'batch': 0,
            'total_found': len(discovered),
            'has_more': has_more,
            'message': f'Found {len(discovered)} groups! Showing first {len(first_batch)}'
        })
        
    except Exception as e:
        logger.error(f"Playwright discovery error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to discover groups. Check logs.'
        }), 500


@app.route('/api/groups/bulk-add', methods=['POST'])
@login_required
def bulk_add_groups():
    """Add multiple groups at once"""
    try:
        data = request.json
        groups_to_add = data.get('groups', [])
        
        if not groups_to_add:
            return jsonify({'success': False, 'error': 'No groups provided'})
        
        # Load existing groups
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            existing_groups = json.load(f)
        
        # Get existing usernames to avoid duplicates
        existing_usernames = {g['username'] for g in existing_groups}
        
        # Add new groups
        added_count = 0
        for group in groups_to_add:
            if group['username'] not in existing_usernames:
                existing_groups.append({
                    'name': group['name'],
                    'username': group['username'],
                    'status': group.get('status', 'member')
                })
                existing_usernames.add(group['username'])
                added_count += 1
        
        # Save updated groups
        with open(f"{PROJECT_ROOT}/groups.json", "w", encoding='utf-8') as f:
            json.dump(existing_groups, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': f'Added {added_count} new groups',
            'total_groups': len(existing_groups),
            'groups': existing_groups
        })
    
    except Exception as e:
        logger.error(f"Bulk add error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/post', methods=['POST'])
@login_required
def create_post():
    try:
        # Handle both JSON and multipart/form-data
        if request.is_json:
            data = request.json
            content = data.get('content', '')
            selected_groups = data.get('groups', [])
            media_files = []
        else:
            # Handle file uploads
            content = request.form.get('content', '')
            selected_groups = request.form.getlist('groups[]')
            selected_groups = [int(g) for g in selected_groups if g.isdigit()]
            
            # Handle uploaded files
            media_files = []
            if 'media' in request.files:
                uploaded_files = request.files.getlist('media')
                for file in uploaded_files:
                    if file and file.filename:
                        # Save file temporarily
                        import os
                        from werkzeug.utils import secure_filename
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(PROJECT_ROOT, 'uploads', filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        file.save(filepath)
                        media_files.append(filepath)
        
        # Save to database
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT INTO posts (content, status, groups_posted) VALUES (?, ?, ?)', (content, 'posting', json.dumps([])))
        post_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Load all groups
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            all_groups = json.load(f)
        
        # Filter selected groups or use all if none selected
        if selected_groups:
            groups_to_post = [all_groups[i] for i in selected_groups if i < len(all_groups)]
        else:
            groups_to_post = all_groups
        
        if not groups_to_post:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('UPDATE posts SET status = ? WHERE id = ?', ('failed', post_id))
            conn.commit()
            conn.close()
            return jsonify({'success': False, 'error': 'No groups selected'})
        
        # Post in background to hide bot movement
        import threading
        def do_post_background(post_id_arg: int, content_arg: str, groups_arg: list, media_files_arg: list):
            try:
                from main import FacebookGroupSpam
                poster = FacebookGroupSpam(post_content=content_arg, headless=True, media_files=media_files_arg if media_files_arg else None)
                poster.start_browser()
                poster.load_cookie()
                # Init active post tracking
                ACTIVE_POSTS[post_id_arg] = {
                    'total': len(groups_arg),
                    'completed': 0,
                    'failed': 0,
                    'start_ts': time.time(),
                    'avg_ms': 0,
                    'last_group': None,
                    'groups': [{'name': g.get('name'), 'username': g.get('username'), 'status': 'pending'} for g in groups_arg],
                    'cancel': False,
                }
                def _progress(ev: Dict):
                    try:
                        ok = bool(ev['result'].get('success'))
                        ACTIVE_POSTS[post_id_arg]['completed'] += 1
                        if not ok:
                            ACTIVE_POSTS[post_id_arg]['failed'] += 1
                        # Update last group and status list
                        ACTIVE_POSTS[post_id_arg]['last_group'] = ev['result'].get('name')
                        idx = ev.get('index', 0)
                        if isinstance(idx, int) and 0 <= idx < len(ACTIVE_POSTS[post_id_arg]['groups']):
                            ACTIVE_POSTS[post_id_arg]['groups'][idx]['status'] = 'done' if ok else 'failed'
                        # Update moving average time per group
                        elapsed = int(ev.get('elapsed_ms', 0))
                        meta = ACTIVE_POSTS[post_id_arg]
                        # Weighted moving average
                        if elapsed > 0:
                            if meta['avg_ms'] == 0:
                                meta['avg_ms'] = elapsed
                            else:
                                meta['avg_ms'] = int((meta['avg_ms'] * 0.7) + (elapsed * 0.3))
                        # Write analytics row per group
                        try:
                            conn_a = sqlite3.connect(DATABASE)
                            c_a = conn_a.cursor()
                            c_a.execute('INSERT INTO post_analytics (post_id, group_name, success, error_message) VALUES (?, ?, ?, ?)', (
                                post_id_arg,
                                ev['result'].get('name') or ev['result'].get('username') or '',
                                1 if ok else 0,
                                (ev['result'].get('error') or '')[:500]
                            ))
                            conn_a.commit()
                            conn_a.close()
                        except Exception:
                            pass
                        # Append successful group name to posts table progressively
                        if ok:
                            conn_p = sqlite3.connect(DATABASE)
                            c_p = conn_p.cursor()
                            c_p.execute('SELECT groups_posted FROM posts WHERE id = ?', (post_id_arg,))
                            row = c_p.fetchone()
                            posted = json.loads(row[0]) if row and row[0] else []
                            posted.append(ev['result']['name'])
                            c_p.execute('UPDATE posts SET groups_posted = ? WHERE id = ?', (json.dumps(posted), post_id_arg))
                            conn_p.commit()
                            conn_p.close()
                    except Exception:
                        pass
                # cancellation check callback
                def _should_cancel():
                    return bool(ACTIVE_POSTS.get(post_id_arg, {}).get('cancel'))
                results = poster.post_to_groups(groups_arg, progress_callback=_progress, should_cancel=_should_cancel)
                poster.close_browser()

                successful_groups = [r['name'] for r in results if r['success']]

                conn_b = sqlite3.connect(DATABASE)
                c_b = conn_b.cursor()
                status_b = 'posted' if successful_groups else 'failed'
                c_b.execute('UPDATE posts SET status = ?, groups_posted = ? WHERE id = ?', (status_b, json.dumps(successful_groups), post_id_arg))
                conn_b.commit()
                conn_b.close()
                # Clear tracking
                ACTIVE_POSTS.pop(post_id_arg, None)
            except Exception as bg_error:
                logger.error(f"Background posting error: {bg_error}")
                import traceback
                logger.error(traceback.format_exc())
                try:
                    conn_b = sqlite3.connect(DATABASE)
                    c_b = conn_b.cursor()
                    c_b.execute('UPDATE posts SET status = ? WHERE id = ?', ('failed', post_id_arg))
                    conn_b.commit()
                    conn_b.close()
                except:
                    pass
                ACTIVE_POSTS.pop(post_id_arg, None)

        thread = threading.Thread(target=do_post_background, args=(post_id, content, groups_to_post, media_files))
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Posting started', 'post_id': post_id})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/history', methods=['GET'])
@login_required
def get_history():
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT id, content, timestamp, status, groups_posted FROM posts ORDER BY timestamp DESC LIMIT 50')
        rows = c.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            posts.append({
                'id': row[0],
                'content': row[1],
                'timestamp': row[2],
                'status': row[3],
                'groups': json.loads(row[4]) if row[4] else []
            })
        
        return jsonify({'success': True, 'posts': posts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/fb-login', methods=['POST'])
@login_required
def fb_login():
    """Trigger Facebook login process"""
    try:
        import subprocess
        import threading
        
        def run_fb_login():
            subprocess.run(['python', 'main.py'], cwd=PROJECT_ROOT, shell=True)
        
        # Run in background thread
        thread = threading.Thread(target=run_fb_login)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Browser window will open. Login and press ENTER in the terminal.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/fb-manual-login', methods=['POST'])
@login_required
def fb_manual_login():
    """Manual login - opens browser for user to login themselves"""
    try:
        import threading
        from main import FacebookGroupSpam
        # Load SOCIAL_MAPS from available config modules, with safe fallback
        try:
            from configs import SOCIAL_MAPS
        except Exception:
            try:
                from config import SOCIAL_MAPS
            except Exception:
                SOCIAL_MAPS = {}
        import json
        import time
        import os
        
        login_status = {'success': False, 'message': '', 'cookies_saved': False}

        def run_manual_login():
            # Open browser and wait for user to complete login, then save cookies automatically
            # Don't set FB_DEBUG - it opens DevTools which is annoying
            poster = FacebookGroupSpam(headless=False)
            try:
                poster.start_browser()
                logger.info("Manual login: browser opened for manual login")
                login_status['message'] = 'Browser opened. Please login to Facebook...'
                
                # Navigate to Facebook
                try:
                    poster.page.goto("https://www.facebook.com", timeout=30000)
                    logger.info("Manual login: navigated to https://www.facebook.com")
                except Exception as e:
                    logger.warning(f"Manual login: navigation to www failed: {e}")
                    try:
                        poster.page.goto("https://m.facebook.com", timeout=30000)
                        logger.info("Manual login: navigated to https://m.facebook.com")
                    except Exception as e2:
                        logger.error(f"Manual login: failed to navigate to Facebook: {e2}")
                        login_status['message'] = 'Failed to navigate to Facebook'
                        return

                # Poll for login cookies (e.g., c_user and xs) up to 5 minutes
                start_time = time.time()
                saved = False
                attempt = 0
                while time.time() - start_time < 300:  # 5 minutes
                    time.sleep(2)
                    attempt += 1
                    try:
                        # Get cookies from all Facebook domains
                        cookies = poster.page.context.cookies(['https://www.facebook.com', 'https://facebook.com', 'https://m.facebook.com'])
                        names = {c.get('name') for c in cookies}
                        logger.info(f"Manual login attempt {attempt}: found cookies: {names}")
                        
                        # Check for Facebook login cookies
                        if 'c_user' in names and 'xs' in names:
                            logger.info("Manual login: detected c_user and xs cookies - LOGIN SUCCESSFUL!")
                            # Save cookies
                            sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')
                            os.makedirs(sessions_dir, exist_ok=True)
                            try:
                                from configs import SOCIAL_MAPS
                            except Exception:
                                try:
                                    from config import SOCIAL_MAPS
                                except Exception:
                                    SOCIAL_MAPS = {}
                            cookie_filename = SOCIAL_MAPS.get('facebook', {}).get('filename', 'facebook-cookies.json')
                            file_path = os.path.join(sessions_dir, cookie_filename)
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(cookies, f, indent=2)
                            logger.info(f"Manual login: saved cookies to {file_path}")

                            # Save debug artifacts (screenshot, html, console) for troubleshooting
                            try:
                                logs_dir = os.path.join(PROJECT_ROOT, 'logs', 'playwright')
                                os.makedirs(logs_dir, exist_ok=True)
                                ts = int(time.time())
                                screenshot = os.path.join(logs_dir, f"manual-login-{ts}.png")
                                htmlfile = os.path.join(logs_dir, f"manual-login-{ts}.html")
                                consolefile = os.path.join(logs_dir, f"manual-login-{ts}-console.log")
                                try:
                                    poster.page.screenshot(path=screenshot, full_page=True)
                                except Exception as e:
                                    logger.debug(f"Manual login screenshot failed: {e}")
                                try:
                                    with open(htmlfile, 'w', encoding='utf-8') as fh:
                                        fh.write(poster.page.content())
                                except Exception as e:
                                    logger.debug(f"Manual login html dump failed: {e}")
                                try:
                                    with open(consolefile, 'w', encoding='utf-8') as cf:
                                        cf.write("\n".join(getattr(poster, 'console_messages', [])))
                                except Exception as e:
                                    logger.debug(f"Manual login write console failed: {e}")
                                logger.info(f"Manual login: saved debug artifacts to {logs_dir}")
                            except Exception as e:
                                logger.debug(f"Manual login: failed saving debug artifacts: {e}")
                            
                            # Also update accounts.json
                            account_file = os.path.join(PROJECT_ROOT, 'accounts.json')
                            try:
                                accounts = []
                                if os.path.exists(account_file):
                                    with open(account_file, 'r', encoding='utf-8') as f:
                                        accounts = json.load(f)
                                
                                # Find c_user value
                                c_user = next((c.get('value') for c in cookies if c.get('name') == 'c_user'), None)
                                if c_user:
                                    # Check if account exists
                                    existing = next((a for a in accounts if a.get('user_id') == c_user), None)
                                    if not existing:
                                        accounts.append({
                                            'user_id': c_user,
                                            'status': 'active',
                                            'cookie_file': (cookie_filename if 'cookie_filename' in locals() else 'facebook-cookies.json'),
                                            'login_date': datetime.now().isoformat()
                                        })
                                    with open(account_file, 'w', encoding='utf-8') as f:
                                        json.dump(accounts, f, indent=2, ensure_ascii=False)
                                    logger.info(f"Manual login: accounts.json updated for user {c_user}")
                            except Exception as e:
                                logger.warning(f"Manual login: failed updating accounts.json: {e}")
                            
                            saved = True
                            login_status['success'] = True
                            login_status['cookies_saved'] = True
                            login_status['message'] = f'Login successful! Cookies saved.'
                            break
                    except Exception as e:
                        logger.debug(f"Manual login: checking cookies attempt {attempt} failed: {e}")
                        login_status['message'] = f'Checking for login... ({attempt})'
                        continue

                if not saved:
                    # Save debug artifacts when timed out
                    try:
                        logs_dir = os.path.join(PROJECT_ROOT, 'logs', 'playwright')
                        os.makedirs(logs_dir, exist_ok=True)
                        ts = int(time.time())
                        screenshot = os.path.join(logs_dir, f"manual-login-timeout-{ts}.png")
                        htmlfile = os.path.join(logs_dir, f"manual-login-timeout-{ts}.html")
                        consolefile = os.path.join(logs_dir, f"manual-login-timeout-{ts}-console.log")
                        try:
                            poster.page.screenshot(path=screenshot, full_page=True)
                        except Exception as e:
                            logger.debug(f"Manual login timeout screenshot failed: {e}")
                        try:
                            with open(htmlfile, 'w', encoding='utf-8') as fh:
                                fh.write(poster.page.content())
                        except Exception as e:
                            logger.debug(f"Manual login timeout html dump failed: {e}")
                        try:
                            with open(consolefile, 'w', encoding='utf-8') as cf:
                                cf.write("\n".join(getattr(poster, 'console_messages', [])))
                        except Exception as e:
                            logger.debug(f"Manual login timeout write console failed: {e}")
                        logger.info(f"Manual login: saved timeout debug artifacts to {logs_dir}")
                    except Exception as e:
                        logger.debug(f"Manual login: failed saving timeout artifacts: {e}")
                    logger.info("Manual login: timed out without cookies")
                    login_status['message'] = 'Login timeout. Cookies were not detected.'
            except Exception as e:
                # Capture debug artifacts on error
                try:
                    logs_dir = os.path.join(PROJECT_ROOT, 'logs', 'playwright')
                    os.makedirs(logs_dir, exist_ok=True)
                    ts = int(time.time())
                    screenshot = os.path.join(logs_dir, f"manual-login-error-{ts}.png")
                    htmlfile = os.path.join(logs_dir, f"manual-login-error-{ts}.html")
                    consolefile = os.path.join(logs_dir, f"manual-login-error-{ts}-console.log")
                    try:
                        poster.page.screenshot(path=screenshot, full_page=True)
                    except Exception as e2:
                        logger.debug(f"Manual login error screenshot failed: {e2}")
                    try:
                        with open(htmlfile, 'w', encoding='utf-8') as fh:
                            fh.write(poster.page.content())
                    except Exception as e2:
                        logger.debug(f"Manual login error html dump failed: {e2}")
                    try:
                        with open(consolefile, 'w', encoding='utf-8') as cf:
                            cf.write("\n".join(getattr(poster, 'console_messages', [])))
                    except Exception as e2:
                        logger.debug(f"Manual login error write console failed: {e2}")
                    logger.info(f"Manual login: saved error debug artifacts to {logs_dir}")
                except Exception as e2:
                    logger.debug(f"Manual login: failed saving error artifacts: {e2}")
                logger.error(f"Manual login error: {e}")
                login_status['message'] = f'Error during login: {str(e)}'
            finally:
                try:
                    poster.close_browser()
                except Exception as e:
                    logger.debug(f"Error closing browser after manual login: {e}")
        
        thread = threading.Thread(target=run_manual_login)
        thread.daemon = True
        thread.start()
        return jsonify({'success': True, 'message': 'Browser opening for manual login. Complete login to save session automatically.', 'check_url': '/api/login-status'})
    except Exception as e:
        logger.exception("Error in /api/fb-manual-login")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/login-status', methods=['GET'])
@login_required
def check_login_status():
    """Check if Facebook cookies are saved and valid"""
    try:
        import os
        import json
        try:
            from configs import SOCIAL_MAPS
        except Exception:
            try:
                from config import SOCIAL_MAPS
            except Exception:
                SOCIAL_MAPS = {}
        cookie_filename = SOCIAL_MAPS.get('facebook', {}).get('filename', 'facebook-cookies.json')
        
        sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')
        cookie_file = os.path.join(sessions_dir, cookie_filename)
        
        if os.path.exists(cookie_file):
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                c_user = next((c.get('value') for c in cookies if c.get('name') == 'c_user'), None)
                xs = next((c.get('value') for c in cookies if c.get('name') == 'xs'), None)
                
                if c_user and xs:
                    return jsonify({
                        'success': True,
                        'logged_in': True,
                        'user_id': c_user,
                        'message': 'Login successful!'
                    })
        
        return jsonify({
            'success': True,
            'logged_in': False,
            'message': 'Not logged in yet'
        })
    except Exception as e:
        logger.exception("Error in /api/login-status")
        return jsonify({
            'success': False,
            'logged_in': False,
            'error': str(e)
        })

@app.route('/manual-login', methods=['GET'])
@login_required
def manual_login_page():
    """Render manual login instructions page"""
    return render_template('manual_login.html')

@app.route('/api/fb-auto-login', methods=['POST'])
@login_required
def fb_auto_login():
    """FAST Auto-login to Facebook with credentials"""
    try:
        import threading
        from main import FacebookGroupSpam
        try:
            from configs import SOCIAL_MAPS
        except Exception:
            try:
                from config import SOCIAL_MAPS
            except Exception:
                SOCIAL_MAPS = {}
        
        data = request.json or {}
        email = data.get('email') or None
        password = data.get('password') or None

        # Fallback to configs
        if not email or not password:
            from configs import FACEBOOK_EMAIL, FACEBOOK_PASSWORD
            email = email or FACEBOOK_EMAIL
            password = password or FACEBOOK_PASSWORD

        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'})
        
        def run_fast_login():
            try:
                # Don't set FB_DEBUG - it opens DevTools
                # Fast login with minimal overhead
                poster = FacebookGroupSpam(headless=False)
                poster.start_browser()
                
                # Execute login
                success = poster.auto_login_with_credentials(email, password)
                
                if success:
                    # Save cookies immediately - get from all Facebook domains
                    try:
                        cookies = poster.page.context.cookies(['https://www.facebook.com', 'https://facebook.com', 'https://m.facebook.com'])
                        sessions_dir = os.path.join(PROJECT_ROOT, 'sessions')
                        os.makedirs(sessions_dir, exist_ok=True)
                        try:
                            cookie_filename = SOCIAL_MAPS.get('facebook', {}).get('filename', 'facebook-cookies.json')
                        except Exception:
                            cookie_filename = 'facebook-cookies.json'
                        file_path = os.path.join(sessions_dir, cookie_filename)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(cookies, f)
                        logger.info(f"Auto login: saved {len(cookies)} cookies to {file_path}")
                        
                        # Quick account update
                        account_file = os.path.join(PROJECT_ROOT, 'accounts.json')
                        try:
                            accounts = []
                            if os.path.exists(account_file):
                                with open(account_file, 'r', encoding='utf-8') as f:
                                    accounts = json.load(f)
                            
                            c_user = next((c.get('value') for c in cookies if c.get('name') == 'c_user'), None)
                            if c_user and not any(a.get('user_id') == c_user for a in accounts):
                                accounts.append({
                                    'user_id': c_user,
                                    'email': email,
                                    'status': 'active'
                                })
                                with open(account_file, 'w', encoding='utf-8') as f:
                                    json.dump(accounts, f)
                        except:
                            pass
                    except Exception as e:
                        logger.error(f"Cookie save error: {e}")
                
                poster.close_browser()
            except Exception as e:
                logger.error(f"Login error: {e}")
        
        # Start in background - non-blocking
        thread = threading.Thread(target=run_fast_login)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Login started...', 'check_url': '/api/login-status'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/session-status', methods=['GET'])
def session_status():
    """Check if Facebook session exists and appears valid (fast check without browser)"""
    session_file = f"{PROJECT_ROOT}/sessions/facebook-cookies.json"
    exists = os.path.exists(session_file)
    
    if not exists:
        return jsonify({'success': True, 'has_session': False, 'valid': False})
    
    # Fast check: just verify cookies file has c_user and xs cookies
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        cookie_names = {c.get('name') for c in cookies}
        has_c_user = 'c_user' in cookie_names
        has_xs = 'xs' in cookie_names
        
        # Get user info
        c_user_value = next((c.get('value') for c in cookies if c.get('name') == 'c_user'), None)
        
        if has_c_user and has_xs:
            return jsonify({
                'success': True, 
                'has_session': True, 
                'valid': True,
                'user_id': c_user_value,
                'message': 'Facebook session is active'
            })
        else:
            return jsonify({
                'success': True, 
                'has_session': True, 
                'valid': False,
                'message': 'Session cookies incomplete'
            })
    except Exception as e:
        return jsonify({'success': True, 'has_session': exists, 'valid': False, 'error': str(e)})

# New enhanced API endpoints
@app.route('/api/post-with-image', methods=['POST'])
@login_required
def post_with_image():
    """Post content with multiple images/videos"""
    try:
        content = request.form.get('content', '')
        selected_groups = json.loads(request.form.get('groups', '[]'))
        
        # Handle multiple file uploads
        media_files = []
        upload_dir = f"{PROJECT_ROOT}/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Get all uploaded files
        uploaded_files = request.files.getlist('media')
        for file in uploaded_files:
            if file.filename:
                file_path = os.path.join(upload_dir, f"{int(datetime.now().timestamp())}_{file.filename}")
                file.save(file_path)
                media_files.append(file_path)
        
        print(f"[*] Uploading {len(media_files)} media files")
        
        # Load groups
        with open(f"{PROJECT_ROOT}/groups.json", "r", encoding='utf-8') as f:
            all_groups = json.load(f)
        
        groups_to_post = [all_groups[i] for i in selected_groups if i < len(all_groups)] if selected_groups else all_groups
        
        # Background posting with media to hide bot movement
        import threading
        def do_post_media_bg(content_arg: str, groups_arg: list, media_files_arg: list):
            try:
                poster = FacebookGroupSpam(post_content=content_arg, media_files=media_files_arg, headless=True)
                poster.start_browser()
                poster.load_cookie()
                poster.post_to_groups(groups_arg)
                poster.close_browser()
            finally:
                for file_path in media_files_arg:
                    try:
                        os.remove(file_path)
                    except:
                        pass
        thread = threading.Thread(target=do_post_media_bg, args=(content, groups_to_post, media_files))
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Posting with media started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule', methods=['POST'])
@login_required
def schedule_post():
    """Schedule a post for later"""
    try:
        data = request.json
        scheduler = PostScheduler()
        
        result = scheduler.add_schedule(
            content=data['content'],
            groups=data['groups'],
            schedule_time=data['schedule_time'],
            image_path=data.get('image_path'),
            recurring=data.get('recurring', False),
            interval_hours=data.get('interval_hours', 24),
            duration_type=data.get('duration_type', 'forever'),
            duration_value=data.get('duration_value', 0)
        )
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule', methods=['GET'])
@login_required
def get_schedules():
    """Get all scheduled posts"""
    try:
        scheduler = PostScheduler()
        schedules = scheduler.get_all_schedules()
        next_post = scheduler.get_next_scheduled_time()
        return jsonify({'success': True, 'schedules': schedules, 'next': next_post})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule/<int:schedule_id>', methods=['DELETE'])
@login_required
def delete_schedule(schedule_id):
    """Delete a scheduled post"""
    try:
        scheduler = PostScheduler()
        success = scheduler.delete_schedule(schedule_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule/<int:schedule_id>/pause', methods=['POST'])
@login_required
def pause_schedule(schedule_id):
    try:
        scheduler = PostScheduler()
        # Set status to paused
        for s in scheduler.schedules:
            if s.get('id') == schedule_id:
                s['status'] = 'paused'
                scheduler.save_schedules()
                return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Schedule not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/schedule/<int:schedule_id>/resume', methods=['POST'])
@login_required
def resume_schedule(schedule_id):
    try:
        scheduler = PostScheduler()
        # Set status back to pending
        for s in scheduler.schedules:
            if s.get('id') == schedule_id:
                s['status'] = 'pending'
                scheduler.save_schedules()
                return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Schedule not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analytics', methods=['GET'])
@login_required
def get_analytics():
    """Get posting analytics"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        
        # Total posts
        c.execute('SELECT COUNT(*) FROM posts WHERE status = "posted"')
        total_posts = c.fetchone()[0]
        
        # Posts by status
        c.execute('SELECT status, COUNT(*) FROM posts GROUP BY status')
        status_counts = dict(c.fetchall())
        
        # Recent activity (last 7 days)
        c.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count 
            FROM posts 
            WHERE timestamp >= DATE('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''')
        daily_posts = [{'date': row[0], 'count': row[1]} for row in c.fetchall()]
        
        # Top groups
        c.execute('''
            SELECT group_name, COUNT(*) as count 
            FROM post_analytics 
            WHERE success = 1 
            GROUP BY group_name 
            ORDER BY count DESC 
            LIMIT 10
        ''')
        top_groups = [{'name': row[0], 'posts': row[1]} for row in c.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_posts': total_posts,
            'status_counts': status_counts,
            'daily_posts': daily_posts,
            'top_groups': top_groups
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/posting-status', methods=['GET'])
@login_required
def posting_status():
    """Return whether any posts are currently in 'posting' status"""
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT id, content FROM posts WHERE status = "posting"')
        rows = c.fetchall()
        conn.close()
        active_details = []
        for row in rows:
            post_id = row[0]
            meta = ACTIVE_POSTS.get(post_id, {'total': 0, 'completed': 0, 'failed': 0})
            remaining = max(0, meta.get('total', 0) - meta.get('completed', 0))
            avg_ms = meta.get('avg_ms', 0)
            eta_ms = remaining * avg_ms if avg_ms > 0 else 0
            # Limit groups list to first 5 entries for UI brevity
            groups_brief = meta.get('groups', [])[:5]
            active_details.append({
                'post_id': post_id,
                'content': row[1],
                'total': meta.get('total', 0),
                'completed': meta.get('completed', 0),
                'failed': meta.get('failed', 0),
                'last_group': meta.get('last_group'),
                'eta_ms': int(eta_ms),
                'groups': groups_brief,
            })
        return jsonify({'success': True, 'posting_count': len(active_details), 'is_posting': len(active_details) > 0, 'active_posts': active_details})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'posting_count': 0, 'is_posting': False})

@app.route('/api/post/cancel/<int:post_id>', methods=['POST'])
@login_required
def cancel_post(post_id: int):
    try:
        if post_id in ACTIVE_POSTS:
            ACTIVE_POSTS[post_id]['cancel'] = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'No active post with that id'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/csv-import', methods=['POST'])
@login_required
def csv_import():
    """Import groups from CSV"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Save CSV temporarily
        csv_path = f"{PROJECT_ROOT}/temp_import.csv"
        file.save(csv_path)
        
        # Load and import
        groups = load_groups_from_csv(csv_path)
        
        if groups:
            with open(f"{PROJECT_ROOT}/groups.json", "w", encoding='utf-8') as f:
                json.dump(groups, f, indent=2, ensure_ascii=False)
            
            os.remove(csv_path)
            return jsonify({'success': True, 'imported': len(groups)})
        else:
            return jsonify({'success': False, 'error': 'No groups found in CSV'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/spintax-preview', methods=['POST'])
@login_required
def spintax_preview():
    """Preview spintax variations"""
    try:
        data = request.json
        content = data.get('content', '')
        variations = [spin_text(content) for _ in range(5)]
        return jsonify({'success': True, 'variations': variations})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== NEW MODULE API ENDPOINTS ====================

# Templates API
@app.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    """Get all content templates"""
    if not template_mgr:
        return jsonify({'success': False, 'error': 'Templates not enabled'})
    try:
        templates = template_mgr.get_all_templates()
        categories = template_mgr.get_categories()
        return jsonify({'success': True, 'templates': templates, 'categories': categories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/templates', methods=['POST'])
@login_required
def create_template():
    """Create a new content template"""
    if not template_mgr:
        return jsonify({'success': False, 'error': 'Templates not enabled'})
    try:
        data = request.json
        result = template_mgr.create_template(
            name=data['name'],
            content=data['content'],
            category=data.get('category', 'general'),
            tags=data.get('tags', []),
            variables=data.get('variables', {})
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/templates/<int:template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    """Update a template"""
    if not template_mgr:
        return jsonify({'success': False, 'error': 'Templates not enabled'})
    try:
        data = request.json
        success = template_mgr.update_template(template_id, data)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/templates/<int:template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    """Delete a template"""
    if not template_mgr:
        return jsonify({'success': False, 'error': 'Templates not enabled'})
    try:
        success = template_mgr.delete_template(template_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/templates/<int:template_id>/render', methods=['POST'])
@login_required
def render_template_content(template_id):
    """Render a template with variables"""
    if not template_mgr:
        return jsonify({'success': False, 'error': 'Templates not enabled'})
    try:
        data = request.json or {}
        variables = data.get('variables', {})
        content = template_mgr.render_template(template_id, variables)
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Drafts API
@app.route('/api/drafts', methods=['GET'])
@login_required
def get_drafts():
    """Get all drafts"""
    if not draft_mgr:
        return jsonify({'success': False, 'error': 'Drafts not enabled'})
    try:
        drafts = draft_mgr.get_all_drafts()
        return jsonify({'success': True, 'drafts': drafts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts', methods=['POST'])
@login_required
def save_draft():
    """Save a draft"""
    if not draft_mgr:
        return jsonify({'success': False, 'error': 'Drafts not enabled'})
    try:
        data = request.json
        result = draft_mgr.create_draft(
            content=data['content'],
            title=data.get('title'),
            groups=data.get('groups', []),
            media_files=data.get('media_ids', [])
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts/<int:draft_id>', methods=['GET'])
@login_required
def get_draft(draft_id):
    """Get a single draft"""
    if not draft_mgr:
        return jsonify({'success': False, 'error': 'Drafts not enabled'})
    try:
        draft = draft_mgr.get_draft(draft_id)
        if draft:
            return jsonify({'success': True, 'draft': draft})
        return jsonify({'success': False, 'error': 'Draft not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/drafts/<int:draft_id>', methods=['DELETE'])
@login_required
def delete_draft(draft_id):
    """Delete a draft"""
    if not draft_mgr:
        return jsonify({'success': False, 'error': 'Drafts not enabled'})
    try:
        success = draft_mgr.delete_draft(draft_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Enhanced Analytics API
@app.route('/api/analytics/daily', methods=['GET'])
@login_required
def get_daily_analytics():
    """Get daily posting statistics"""
    if not analytics_mgr:
        return jsonify({'success': False, 'error': 'Analytics not enabled'})
    try:
        days = request.args.get('days', 30, type=int)
        stats = analytics_mgr.get_daily_stats(days=days)
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analytics/hourly', methods=['GET'])
@login_required
def get_hourly_analytics():
    """Get hourly distribution"""
    if not analytics_mgr:
        return jsonify({'success': False, 'error': 'Analytics not enabled'})
    try:
        days = request.args.get('days', 30, type=int)
        stats = analytics_mgr.get_hourly_distribution(days=days)
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analytics/groups', methods=['GET'])
@login_required
def get_group_analytics():
    """Get group performance analytics"""
    if not analytics_mgr:
        return jsonify({'success': False, 'error': 'Analytics not enabled'})
    try:
        performance = analytics_mgr.get_group_performance()
        return jsonify({'success': True, 'groups': performance})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analytics/export', methods=['GET'])
@login_required
def export_analytics():
    """Export analytics to CSV"""
    if not analytics_mgr:
        return jsonify({'success': False, 'error': 'Analytics not enabled'})
    try:
        days = request.args.get('days', 30, type=int)
        csv_data = analytics_mgr.export_to_csv(days=days)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=analytics.csv'}
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/analytics/best-times', methods=['GET'])
@login_required
def get_best_posting_times():
    """Get best posting times analysis"""
    if not analytics_mgr:
        return jsonify({'success': False, 'error': 'Analytics not enabled'})
    try:
        times = analytics_mgr.get_best_posting_times()
        return jsonify({'success': True, 'best_times': times})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Media Library API
@app.route('/api/media', methods=['GET'])
@login_required
def get_media():
    """Get media library files"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        media_type = request.args.get('type')
        collection = request.args.get('collection')
        search = request.args.get('search')
        
        if search:
            files = media_lib.search_files(search)
        elif collection:
            files = media_lib.get_files_by_collection(collection)
        else:
            files = media_lib.get_all_files(media_type=media_type)
        
        stats = media_lib.get_stats()
        return jsonify({'success': True, 'files': files, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media', methods=['POST'])
@login_required
def upload_media():
    """Upload media to library"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['file']
        name = request.form.get('name', file.filename)
        tags = request.form.get('tags', '').split(',')
        tags = [t.strip() for t in tags if t.strip()]
        collection = request.form.get('collection')
        
        # Ensure uploads directory exists
        uploads_dir = os.path.join(PROJECT_ROOT, 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save temporarily
        temp_path = os.path.join(uploads_dir, file.filename)
        file.save(temp_path)
        
        # Add to library
        result = media_lib.add_file(temp_path, name=name, tags=tags, collection=collection)
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except:
            pass
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media/<file_id>', methods=['GET'])
@login_required
def get_media_file(file_id):
    """Get a single media file info"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        file_info = media_lib.get_file(file_id)
        if file_info:
            return jsonify({'success': True, 'file': file_info})
        return jsonify({'success': False, 'error': 'File not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media/<file_id>', methods=['PUT'])
@login_required
def update_media(file_id):
    """Update media file metadata"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        data = request.json
        success = media_lib.update_file(file_id, data)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media/<file_id>', methods=['DELETE'])
@login_required
def delete_media(file_id):
    """Delete media from library"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        success = media_lib.delete_file(file_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media/collections', methods=['GET'])
@login_required
def get_media_collections():
    """Get media collections"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        collections = media_lib.get_collections()
        return jsonify({'success': True, 'collections': collections})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media/collections', methods=['POST'])
@login_required
def create_media_collection():
    """Create a media collection"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        data = request.json
        result = media_lib.create_collection(data['name'], data.get('description'))
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/media/collections/<name>', methods=['DELETE'])
@login_required
def delete_media_collection(name):
    """Delete a media collection"""
    if not media_lib:
        return jsonify({'success': False, 'error': 'Media library not enabled'})
    try:
        success = media_lib.delete_collection(name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Multi-Account API
@app.route('/api/accounts', methods=['GET'])
@login_required
def get_accounts():
    """Get all Facebook accounts"""
    if not account_mgr:
        return jsonify({'success': False, 'error': 'Multi-account not enabled'})
    try:
        accounts = account_mgr.get_all_accounts()
        summary = account_mgr.get_accounts_summary()
        return jsonify({'success': True, 'accounts': accounts, 'summary': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts', methods=['POST'])
@login_required
def add_account():
    """Add a new Facebook account"""
    if not account_mgr:
        return jsonify({'success': False, 'error': 'Multi-account not enabled'})
    try:
        data = request.json
        result = account_mgr.add_account(
            name=data['name'],
            email=data.get('email'),
            notes=data.get('notes')
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<account_id>', methods=['PUT'])
@login_required
def update_account(account_id):
    """Update an account"""
    if not account_mgr:
        return jsonify({'success': False, 'error': 'Multi-account not enabled'})
    try:
        data = request.json
        success = account_mgr.update_account(account_id, data)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<account_id>/switch', methods=['POST'])
@login_required
def switch_account(account_id):
    """Switch to a different account"""
    if not account_mgr:
        return jsonify({'success': False, 'error': 'Multi-account not enabled'})
    try:
        success = account_mgr.switch_account(account_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
@login_required
def delete_account(account_id):
    """Delete an account"""
    if not account_mgr:
        return jsonify({'success': False, 'error': 'Multi-account not enabled'})
    try:
        success = account_mgr.delete_account(account_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/accounts/<account_id>/save-session', methods=['POST'])
@login_required
def save_account_session(account_id):
    """Save current session to an account"""
    if not account_mgr:
        return jsonify({'success': False, 'error': 'Multi-account not enabled'})
    try:
        success = account_mgr.save_session_for_account(account_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Backup API
@app.route('/api/backups', methods=['GET'])
@login_required
def list_backups():
    """List available backups"""
    if not backup_mgr:
        # Return empty list if backup not enabled, but still succeed
        return jsonify({'success': True, 'backups': [], 'message': 'Backup not enabled'})
    try:
        backups = backup_mgr.list_backups()
        return jsonify({'success': True, 'backups': backups})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/backups', methods=['POST'])
@login_required
def create_backup():
    """Create a backup"""
    if not backup_mgr:
        return jsonify({'success': False, 'error': 'Backup not enabled'})
    try:
        # Backup session files
        session_files = [
            os.path.join(PROJECT_ROOT, 'sessions', 'facebook-cookies.json'),
            os.path.join(PROJECT_ROOT, 'groups.json'),
            DATABASE
        ]
        backup_name = backup_mgr.create_backup(
            [f for f in session_files if os.path.exists(f)]
        )
        return jsonify({'success': True, 'name': backup_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/backups/<name>/restore', methods=['POST'])
@login_required
def restore_backup(name):
    """Restore from backup"""
    if not backup_mgr:
        return jsonify({'success': False, 'error': 'Backup not enabled'})
    try:
        success = backup_mgr.restore_backup(name)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# Rate Limit Status API
@app.route('/api/rate-limit', methods=['GET'])
@login_required
def get_rate_limit_status():
    """Get current rate limit status"""
    if not rate_limiter:
        return jsonify({'success': False, 'error': 'Rate limiter not enabled'})
    try:
        account_id = request.args.get('account', 'default')
        can_post, wait_time, message = rate_limiter.can_post(account_id)
        return jsonify({
            'success': True,
            'can_post': can_post,
            'wait_seconds': wait_time,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# System Info API
@app.route('/api/system/config', methods=['GET'])
@login_required
def get_system_config():
    """Get system configuration (masked)"""
    try:
        config = get_config_summary()
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/system/features', methods=['GET'])
@login_required
def get_enabled_features():
    """Get enabled features"""
    return jsonify({
        'success': True,
        'features': {
            'multi_account': account_mgr is not None,
            'media_library': media_lib is not None,
            'templates': template_mgr is not None,
            'drafts': draft_mgr is not None,
            'analytics': analytics_mgr is not None,
            'backups': backup_mgr is not None,
            'rate_limiting': rate_limiter is not None,
            'api_docs': api_docs is not None
        }
    })


@app.route('/api/clear-all-data', methods=['POST'])
@login_required
def clear_all_data():
    """Clear all groups and post history - start fresh"""
    try:
        results = {
            'groups_cleared': False,
            'database_cleared': False,
            'errors': []
        }
        
        # 1. Clear groups.json
        groups_file = os.path.join(PROJECT_ROOT, 'groups.json')
        try:
            with open(groups_file, 'w') as f:
                json.dump([], f)
            results['groups_cleared'] = True
            logger.info("[CLEAR DATA] Groups cleared")
        except Exception as e:
            results['errors'].append(f"Groups: {str(e)}")
            logger.error(f"[CLEAR DATA] Failed to clear groups: {e}")
        
        # 2. Clear database tables (posts and analytics)
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('DELETE FROM posts')
            c.execute('DELETE FROM analytics')
            conn.commit()
            conn.close()
            results['database_cleared'] = True
            logger.info("[CLEAR DATA] Database cleared")
        except Exception as e:
            results['errors'].append(f"Database: {str(e)}")
            logger.error(f"[CLEAR DATA] Failed to clear database: {e}")
        
        success = results['groups_cleared'] and results['database_cleared']
        
        return jsonify({
            'success': success,
            'message': 'All data cleared! You can now discover new groups.' if success else 'Partial clear',
            'results': results
        })
        
    except Exception as e:
        logger.error(f"[CLEAR DATA] Error: {e}")
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    init_db()
    host = os.environ.get('HOST', SERVER_HOST)
    port = int(os.environ.get('PORT', SERVER_PORT))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true' or DEBUG_MODE
    
    # Use production server if available
    use_production = os.environ.get('PRODUCTION', 'false').lower() == 'true'
    
    if use_production:
        try:
            from waitress import serve
            logger.info(f"Starting production server on {host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            logger.warning("Waitress not installed, falling back to Flask dev server")
            app.run(debug=debug, host=host, port=port, use_reloader=False)
    else:
        logger.info(f"Starting development server on {host}:{port}")
        app.run(debug=debug, host=host, port=port, use_reloader=False)
