"""
MongoDB Database Module for Persistent Data Storage
Handles users, cookies, groups, accounts, settings, and posts data
"""
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from functools import wraps

# Password hashing
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    print("[MongoDB] bcrypt not installed, password hashing unavailable")

# MongoDB connection
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoClient = None

# Get MongoDB URI from environment or use default
MONGODB_URI = os.environ.get('MONGODB_URI', '')
DATABASE_NAME = os.environ.get('MONGODB_DATABASE', 'fb_auto_poster')

# Global database connection
_db_client = None
_db = None

def get_db():
    """Get MongoDB database connection (singleton pattern)"""
    global _db_client, _db
    
    if not PYMONGO_AVAILABLE:
        print("[MongoDB] pymongo not installed, using file-based storage")
        return None
    
    if not MONGODB_URI:
        print("[MongoDB] MONGODB_URI not set, using file-based storage")
        return None
    
    if _db is None:
        try:
            _db_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            _db_client.admin.command('ping')
            _db = _db_client[DATABASE_NAME]
            print(f"[MongoDB] Connected successfully to database: {DATABASE_NAME}")
        except Exception as e:
            print(f"[MongoDB] Connection failed: {e}")
            _db = None
    
    return _db


def is_mongodb_connected() -> bool:
    """Check if MongoDB is connected and available"""
    db = get_db()
    return db is not None


# ============== USER MANAGEMENT ==============

def create_user(username: str, email: str, password: str, role: str = 'user') -> Optional[Dict]:
    """Create a new user with hashed password. Returns user dict or None if failed."""
    db = get_db()
    if db is None:
        print("[MongoDB] Cannot create user - database not connected")
        return None
    
    if not BCRYPT_AVAILABLE:
        print("[MongoDB] Cannot create user - bcrypt not installed")
        return None
    
    try:
        collection = db.users
        
        # Check if email already exists
        if collection.find_one({'email': email.lower()}):
            print(f"[MongoDB] User with email {email} already exists")
            return None
        
        # Check if username already exists
        if collection.find_one({'username': username.lower()}):
            print(f"[MongoDB] User with username {username} already exists")
            return None
        
        # Hash password
        salt = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Create user document
        user_id = str(uuid.uuid4())
        user = {
            'user_id': user_id,
            'username': username.lower(),
            'email': email.lower(),
            'password_hash': password_hash,
            'role': role,  # 'admin' or 'user'
            'created_at': datetime.utcnow(),
            'last_login': None,
            'is_active': True
        }
        
        collection.insert_one(user)
        print(f"[MongoDB] Created user: {username} ({email})")
        
        # Return user without password hash
        user.pop('password_hash', None)
        user.pop('_id', None)
        return user
        
    except Exception as e:
        print(f"[MongoDB] Error creating user: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email address"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.users
        user = collection.find_one({'email': email.lower()})
        if user:
            user.pop('_id', None)
            return user
        return None
    except Exception as e:
        print(f"[MongoDB] Error getting user by email: {e}")
        return None


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by user_id"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.users
        user = collection.find_one({'user_id': user_id})
        if user:
            user.pop('_id', None)
            return user
        return None
    except Exception as e:
        print(f"[MongoDB] Error getting user by id: {e}")
        return None


def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user by username"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.users
        user = collection.find_one({'username': username.lower()})
        if user:
            user.pop('_id', None)
            return user
        return None
    except Exception as e:
        print(f"[MongoDB] Error getting user by username: {e}")
        return None


def verify_user_password(email: str, password: str) -> Optional[Dict]:
    """Verify user password and return user if valid"""
    if not BCRYPT_AVAILABLE:
        print("[MongoDB] Cannot verify password - bcrypt not installed")
        return None
    
    user = get_user_by_email(email)
    if not user:
        return None
    
    try:
        password_hash = user.get('password_hash', '')
        if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
            # Update last login
            update_user_last_login(user['user_id'])
            # Return user without password hash
            user.pop('password_hash', None)
            return user
        return None
    except Exception as e:
        print(f"[MongoDB] Error verifying password: {e}")
        return None


def update_user_last_login(user_id: str) -> bool:
    """Update user's last login timestamp"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.users
        collection.update_one(
            {'user_id': user_id},
            {'$set': {'last_login': datetime.utcnow()}}
        )
        return True
    except Exception as e:
        print(f"[MongoDB] Error updating last login: {e}")
        return False


def update_user(user_id: str, updates: Dict) -> bool:
    """Update user fields (except password)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        # Don't allow password updates through this function
        updates.pop('password_hash', None)
        updates.pop('password', None)
        updates['updated_at'] = datetime.utcnow()
        
        collection = db.users
        result = collection.update_one(
            {'user_id': user_id},
            {'$set': updates}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"[MongoDB] Error updating user: {e}")
        return False


def change_user_password(user_id: str, new_password: str) -> bool:
    """Change user's password"""
    db = get_db()
    if db is None or not BCRYPT_AVAILABLE:
        return False
    
    try:
        salt = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
        
        collection = db.users
        result = collection.update_one(
            {'user_id': user_id},
            {'$set': {'password_hash': password_hash, 'updated_at': datetime.utcnow()}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"[MongoDB] Error changing password: {e}")
        return False


def get_all_users(include_inactive: bool = False) -> List[Dict]:
    """Get all users (admin function)"""
    db = get_db()
    if db is None:
        return []
    
    try:
        collection = db.users
        query = {} if include_inactive else {'is_active': True}
        users = list(collection.find(query))
        
        # Remove sensitive data
        for user in users:
            user.pop('_id', None)
            user.pop('password_hash', None)
        
        return users
    except Exception as e:
        print(f"[MongoDB] Error getting all users: {e}")
        return []


def count_users() -> int:
    """Count total users"""
    db = get_db()
    if db is None:
        return 0
    
    try:
        return db.users.count_documents({'is_active': True})
    except Exception as e:
        print(f"[MongoDB] Error counting users: {e}")
        return 0


# ============== COOKIES STORAGE ==============

def save_cookies_to_db(cookies: List[Dict], account_id: str = 'default', user_id: str = None) -> bool:
    """Save cookies to MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.cookies
        query = {'account_id': account_id}
        if user_id:
            query['user_id'] = user_id
        
        collection.update_one(
            query,
            {
                '$set': {
                    'account_id': account_id,
                    'user_id': user_id,
                    'cookies': cookies,
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        print(f"[MongoDB] Saved {len(cookies)} cookies for account: {account_id}, user: {user_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving cookies: {e}")
        return False


def load_cookies_from_db(account_id: str = 'default', user_id: str = None) -> Optional[List[Dict]]:
    """Load cookies from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.cookies
        query = {'account_id': account_id}
        if user_id:
            query['user_id'] = user_id
        
        doc = collection.find_one(query)
        if doc and 'cookies' in doc:
            print(f"[MongoDB] Loaded {len(doc['cookies'])} cookies for account: {account_id}, user: {user_id}")
            return doc['cookies']
        return None
    except Exception as e:
        print(f"[MongoDB] Error loading cookies: {e}")
        return None


def delete_cookies_from_db(account_id: str = 'default', user_id: str = None) -> bool:
    """Delete cookies from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.cookies
        query = {'account_id': account_id}
        if user_id:
            query['user_id'] = user_id
        
        result = collection.delete_one(query)
        print(f"[MongoDB] Deleted cookies for account: {account_id}, user: {user_id}")
        return result.deleted_count > 0
    except Exception as e:
        print(f"[MongoDB] Error deleting cookies: {e}")
        return False


def delete_all_cookies_from_db(user_id: str = None) -> bool:
    """Delete all cookies from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.cookies
        query = {'user_id': user_id} if user_id else {}
        result = collection.delete_many(query)
        print(f"[MongoDB] Deleted cookies ({result.deleted_count} documents) for user: {user_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error deleting all cookies: {e}")
        return False


# ============== GROUPS STORAGE ==============

def save_groups_to_db(groups: List[Dict], user_id: str = None) -> bool:
    """Save groups list to MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        # Clear existing for this user and insert new
        query = {'user_id': user_id} if user_id else {'user_id': None}
        collection.delete_many(query)
        
        if groups:
            for i, group in enumerate(groups):
                group['_order'] = i
                group['user_id'] = user_id
            collection.insert_many(groups)
        print(f"[MongoDB] Saved {len(groups)} groups for user: {user_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving groups: {e}")
        return False


def load_groups_from_db(user_id: str = None) -> Optional[List[Dict]]:
    """Load groups list from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.groups
        query = {'user_id': user_id} if user_id else {'user_id': None}
        groups = list(collection.find(query).sort('_order', 1))
        
        for group in groups:
            group.pop('_id', None)
            group.pop('_order', None)
            group.pop('user_id', None)
        print(f"[MongoDB] Loaded {len(groups)} groups for user: {user_id}")
        return groups
    except Exception as e:
        print(f"[MongoDB] Error loading groups: {e}")
        return None


def add_group_to_db(group: Dict, user_id: str = None) -> bool:
    """Add a single group to MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        query = {'user_id': user_id} if user_id else {'user_id': None}
        max_order_doc = collection.find_one(query, sort=[('_order', -1)])
        new_order = (max_order_doc.get('_order', 0) + 1) if max_order_doc else 0
        group['_order'] = new_order
        group['user_id'] = user_id
        collection.insert_one(group)
        print(f"[MongoDB] Added group: {group.get('name', 'unknown')} for user: {user_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error adding group: {e}")
        return False


def update_group_in_db(username: str, updates: Dict, user_id: str = None) -> bool:
    """Update a group in MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        query = {'username': username}
        if user_id:
            query['user_id'] = user_id
        
        result = collection.update_one(query, {'$set': updates})
        print(f"[MongoDB] Updated group: {username} for user: {user_id}")
        return result.modified_count > 0
    except Exception as e:
        print(f"[MongoDB] Error updating group: {e}")
        return False


def delete_group_from_db(username: str, user_id: str = None) -> bool:
    """Delete a group from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        query = {'username': username}
        if user_id:
            query['user_id'] = user_id
        
        result = collection.delete_one(query)
        print(f"[MongoDB] Deleted group: {username} for user: {user_id}")
        return result.deleted_count > 0
    except Exception as e:
        print(f"[MongoDB] Error deleting group: {e}")
        return False


# ============== FB ACCOUNTS STORAGE ==============

def save_fb_accounts_to_db(accounts: List[Dict], user_id: str = None) -> bool:
    """Save Facebook accounts list to MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.fb_accounts
        query = {'user_id': user_id} if user_id else {'user_id': None}
        collection.delete_many(query)
        
        if accounts:
            for account in accounts:
                account['user_id'] = user_id
            collection.insert_many(accounts)
        print(f"[MongoDB] Saved {len(accounts)} FB accounts for user: {user_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving accounts: {e}")
        return False


def load_fb_accounts_from_db(user_id: str = None) -> Optional[List[Dict]]:
    """Load Facebook accounts list from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.fb_accounts
        query = {'user_id': user_id} if user_id else {'user_id': None}
        accounts = list(collection.find(query))
        
        for account in accounts:
            account.pop('_id', None)
            account.pop('user_id', None)
        print(f"[MongoDB] Loaded {len(accounts)} FB accounts for user: {user_id}")
        return accounts
    except Exception as e:
        print(f"[MongoDB] Error loading accounts: {e}")
        return None


def delete_all_fb_accounts_from_db(user_id: str = None) -> bool:
    """Delete all Facebook accounts from MongoDB (per-user if user_id provided)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.fb_accounts
        query = {'user_id': user_id} if user_id else {}
        result = collection.delete_many(query)
        print(f"[MongoDB] Deleted FB accounts ({result.deleted_count} documents) for user: {user_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error deleting accounts: {e}")
        return False


# Legacy aliases for backward compatibility
def save_accounts_to_db(accounts: List[Dict], user_id: str = None) -> bool:
    """Alias for save_fb_accounts_to_db"""
    return save_fb_accounts_to_db(accounts, user_id)

def load_accounts_from_db(user_id: str = None) -> Optional[List[Dict]]:
    """Alias for load_fb_accounts_from_db"""
    return load_fb_accounts_from_db(user_id)

def delete_all_accounts_from_db(user_id: str = None) -> bool:
    """Alias for delete_all_fb_accounts_from_db"""
    return delete_all_fb_accounts_from_db(user_id)


# ============== SETTINGS STORAGE ==============

def save_setting_to_db(key: str, value: Any) -> bool:
    """Save a setting to MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.settings
        collection.update_one(
            {'key': key},
            {
                '$set': {
                    'key': key,
                    'value': value,
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        print(f"[MongoDB] Saved setting: {key}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving setting: {e}")
        return False


def load_setting_from_db(key: str, default: Any = None) -> Any:
    """Load a setting from MongoDB"""
    db = get_db()
    if db is None:
        return default
    
    try:
        collection = db.settings
        doc = collection.find_one({'key': key})
        if doc:
            return doc.get('value', default)
        return default
    except Exception as e:
        print(f"[MongoDB] Error loading setting: {e}")
        return default


# ============== POSTS HISTORY STORAGE ==============

def save_post_to_db(post: Dict) -> Optional[str]:
    """Save a post to MongoDB, returns the post ID"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.posts
        post['created_at'] = datetime.utcnow()
        result = collection.insert_one(post)
        print(f"[MongoDB] Saved post with ID: {result.inserted_id}")
        return str(result.inserted_id)
    except Exception as e:
        print(f"[MongoDB] Error saving post: {e}")
        return None


def get_posts_from_db(limit: int = 100, skip: int = 0) -> Optional[List[Dict]]:
    """Get posts from MongoDB with pagination"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.posts
        posts = list(collection.find({}).sort('created_at', -1).skip(skip).limit(limit))
        for post in posts:
            post['_id'] = str(post['_id'])
        print(f"[MongoDB] Loaded {len(posts)} posts")
        return posts
    except Exception as e:
        print(f"[MongoDB] Error loading posts: {e}")
        return None


def update_post_in_db(post_id: str, updates: Dict) -> bool:
    """Update a post in MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        from bson import ObjectId
        collection = db.posts
        result = collection.update_one(
            {'_id': ObjectId(post_id)},
            {'$set': updates}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"[MongoDB] Error updating post: {e}")
        return False


# ============== TEMPLATES STORAGE ==============

def save_templates_to_db(templates: List[Dict]) -> bool:
    """Save content templates to MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.templates
        collection.delete_many({})
        if templates:
            collection.insert_many(templates)
        print(f"[MongoDB] Saved {len(templates)} templates")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving templates: {e}")
        return False


def load_templates_from_db() -> Optional[List[Dict]]:
    """Load content templates from MongoDB"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.templates
        templates = list(collection.find({}))
        for template in templates:
            template.pop('_id', None)
        print(f"[MongoDB] Loaded {len(templates)} templates")
        return templates
    except Exception as e:
        print(f"[MongoDB] Error loading templates: {e}")
        return None


# ============== CREDENTIALS STORAGE ==============

def save_credentials_to_db(email: str, password: str, account_id: str = 'default') -> bool:
    """Save Facebook credentials to MongoDB (encrypted recommended)"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.credentials
        collection.update_one(
            {'account_id': account_id},
            {
                '$set': {
                    'account_id': account_id,
                    'email': email,
                    'password': password,  # Consider encrypting this
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        print(f"[MongoDB] Saved credentials for account: {account_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving credentials: {e}")
        return False


def load_credentials_from_db(account_id: str = 'default') -> Optional[Dict]:
    """Load Facebook credentials from MongoDB"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.credentials
        doc = collection.find_one({'account_id': account_id})
        if doc:
            return {
                'email': doc.get('email'),
                'password': doc.get('password')
            }
        return None
    except Exception as e:
        print(f"[MongoDB] Error loading credentials: {e}")
        return None


# ============== SYNC UTILITIES ==============

def sync_file_to_mongodb(file_path: str, data_type: str) -> bool:
    """
    Sync a local JSON file to MongoDB
    data_type: 'cookies', 'groups', 'accounts', 'templates'
    """
    if not os.path.exists(file_path):
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if data_type == 'cookies':
            return save_cookies_to_db(data)
        elif data_type == 'groups':
            return save_groups_to_db(data)
        elif data_type == 'accounts':
            return save_accounts_to_db(data)
        elif data_type == 'templates':
            return save_templates_to_db(data)
        
        return False
    except Exception as e:
        print(f"[MongoDB] Error syncing file {file_path}: {e}")
        return False


def sync_mongodb_to_file(file_path: str, data_type: str) -> bool:
    """
    Sync MongoDB data to a local JSON file (for backup/compatibility)
    data_type: 'cookies', 'groups', 'accounts', 'templates'
    """
    try:
        data = None
        
        if data_type == 'cookies':
            data = load_cookies_from_db()
        elif data_type == 'groups':
            data = load_groups_from_db()
        elif data_type == 'accounts':
            data = load_accounts_from_db()
        elif data_type == 'templates':
            data = load_templates_from_db()
        
        if data is not None:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        
        return False
    except Exception as e:
        print(f"[MongoDB] Error syncing to file {file_path}: {e}")
        return False


def get_mongodb_status() -> Dict:
    """Get MongoDB connection status and stats"""
    db = get_db()
    
    if db is None:
        return {
            'connected': False,
            'message': 'MongoDB not connected (using file-based storage)',
            'pymongo_available': PYMONGO_AVAILABLE,
            'uri_set': bool(MONGODB_URI)
        }
    
    try:
        # Get collection stats
        stats = {
            'connected': True,
            'database': DATABASE_NAME,
            'collections': {
                'cookies': db.cookies.count_documents({}),
                'groups': db.groups.count_documents({}),
                'accounts': db.accounts.count_documents({}),
                'settings': db.settings.count_documents({}),
                'posts': db.posts.count_documents({}),
                'templates': db.templates.count_documents({})
            }
        }
        return stats
    except Exception as e:
        return {
            'connected': False,
            'error': str(e)
        }


# Initialize connection on module load
print("[MongoDB] Database module loaded")
if MONGODB_URI:
    print("[MongoDB] URI found, attempting connection...")
    get_db()
else:
    print("[MongoDB] No MONGODB_URI set, will use file-based storage")
