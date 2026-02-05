"""
MongoDB Database Module for Persistent Data Storage
Handles cookies, groups, accounts, settings, and posts data
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from functools import wraps

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


# ============== COOKIES STORAGE ==============

def save_cookies_to_db(cookies: List[Dict], account_id: str = 'default') -> bool:
    """Save cookies to MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.cookies
        collection.update_one(
            {'account_id': account_id},
            {
                '$set': {
                    'account_id': account_id,
                    'cookies': cookies,
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=True
        )
        print(f"[MongoDB] Saved {len(cookies)} cookies for account: {account_id}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving cookies: {e}")
        return False


def load_cookies_from_db(account_id: str = 'default') -> Optional[List[Dict]]:
    """Load cookies from MongoDB"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.cookies
        doc = collection.find_one({'account_id': account_id})
        if doc and 'cookies' in doc:
            print(f"[MongoDB] Loaded {len(doc['cookies'])} cookies for account: {account_id}")
            return doc['cookies']
        return None
    except Exception as e:
        print(f"[MongoDB] Error loading cookies: {e}")
        return None


def delete_cookies_from_db(account_id: str = 'default') -> bool:
    """Delete cookies from MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.cookies
        result = collection.delete_one({'account_id': account_id})
        print(f"[MongoDB] Deleted cookies for account: {account_id}")
        return result.deleted_count > 0
    except Exception as e:
        print(f"[MongoDB] Error deleting cookies: {e}")
        return False


def delete_all_cookies_from_db() -> bool:
    """Delete all cookies from MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.cookies
        result = collection.delete_many({})
        print(f"[MongoDB] Deleted all cookies ({result.deleted_count} documents)")
        return True
    except Exception as e:
        print(f"[MongoDB] Error deleting all cookies: {e}")
        return False


# ============== GROUPS STORAGE ==============

def save_groups_to_db(groups: List[Dict]) -> bool:
    """Save groups list to MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        # Clear existing and insert new (atomic replacement)
        collection.delete_many({})
        if groups:
            # Add _id to prevent duplicate issues
            for i, group in enumerate(groups):
                group['_order'] = i  # Preserve order
            collection.insert_many(groups)
        print(f"[MongoDB] Saved {len(groups)} groups")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving groups: {e}")
        return False


def load_groups_from_db() -> Optional[List[Dict]]:
    """Load groups list from MongoDB"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.groups
        groups = list(collection.find({}).sort('_order', 1))
        # Remove MongoDB _id and _order fields for compatibility
        for group in groups:
            group.pop('_id', None)
            group.pop('_order', None)
        print(f"[MongoDB] Loaded {len(groups)} groups")
        return groups
    except Exception as e:
        print(f"[MongoDB] Error loading groups: {e}")
        return None


def add_group_to_db(group: Dict) -> bool:
    """Add a single group to MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        # Get max order
        max_order_doc = collection.find_one(sort=[('_order', -1)])
        new_order = (max_order_doc.get('_order', 0) + 1) if max_order_doc else 0
        group['_order'] = new_order
        collection.insert_one(group)
        print(f"[MongoDB] Added group: {group.get('name', 'unknown')}")
        return True
    except Exception as e:
        print(f"[MongoDB] Error adding group: {e}")
        return False


def update_group_in_db(username: str, updates: Dict) -> bool:
    """Update a group in MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        result = collection.update_one(
            {'username': username},
            {'$set': updates}
        )
        print(f"[MongoDB] Updated group: {username}")
        return result.modified_count > 0
    except Exception as e:
        print(f"[MongoDB] Error updating group: {e}")
        return False


def delete_group_from_db(username: str) -> bool:
    """Delete a group from MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.groups
        result = collection.delete_one({'username': username})
        print(f"[MongoDB] Deleted group: {username}")
        return result.deleted_count > 0
    except Exception as e:
        print(f"[MongoDB] Error deleting group: {e}")
        return False


# ============== ACCOUNTS STORAGE ==============

def save_accounts_to_db(accounts: List[Dict]) -> bool:
    """Save accounts list to MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.accounts
        collection.delete_many({})
        if accounts:
            collection.insert_many(accounts)
        print(f"[MongoDB] Saved {len(accounts)} accounts")
        return True
    except Exception as e:
        print(f"[MongoDB] Error saving accounts: {e}")
        return False


def load_accounts_from_db() -> Optional[List[Dict]]:
    """Load accounts list from MongoDB"""
    db = get_db()
    if db is None:
        return None
    
    try:
        collection = db.accounts
        accounts = list(collection.find({}))
        for account in accounts:
            account.pop('_id', None)
        print(f"[MongoDB] Loaded {len(accounts)} accounts")
        return accounts
    except Exception as e:
        print(f"[MongoDB] Error loading accounts: {e}")
        return None


def delete_all_accounts_from_db() -> bool:
    """Delete all accounts from MongoDB"""
    db = get_db()
    if db is None:
        return False
    
    try:
        collection = db.accounts
        result = collection.delete_many({})
        print(f"[MongoDB] Deleted all accounts ({result.deleted_count} documents)")
        return True
    except Exception as e:
        print(f"[MongoDB] Error deleting accounts: {e}")
        return False


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
