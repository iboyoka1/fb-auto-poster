"""
Media library for managing reusable images and videos
"""
import os
import json
import shutil
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import mimetypes

try:
    from config import PROJECT_ROOT, ENABLE_MEDIA_LIBRARY
except ImportError:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    ENABLE_MEDIA_LIBRARY = True

try:
    from logger import get_logger
    logger = get_logger("media")
except ImportError:
    import logging
    logger = logging.getLogger("media")


ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
    'video': ['.mp4', '.mov', '.avi', '.webm'],
}

MAX_FILE_SIZE_MB = 100  # Maximum file size in MB


class MediaLibrary:
    """
    Manage reusable media files for posts
    """
    
    def __init__(self, media_dir: str = None, metadata_file: str = None):
        self.media_dir = media_dir or os.path.join(PROJECT_ROOT, "media_library")
        self.metadata_file = metadata_file or os.path.join(self.media_dir, "metadata.json")
        self.metadata = self.load_metadata()
        
        # Ensure directories exist
        os.makedirs(self.media_dir, exist_ok=True)
        os.makedirs(os.path.join(self.media_dir, "images"), exist_ok=True)
        os.makedirs(os.path.join(self.media_dir, "videos"), exist_ok=True)
    
    def load_metadata(self) -> Dict:
        """Load media metadata"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {'files': [], 'collections': []}
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return {'files': [], 'collections': []}
    
    def save_metadata(self) -> bool:
        """Save media metadata"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            return False
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate file hash for deduplication"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _get_media_type(self, filename: str) -> Optional[str]:
        """Determine media type from filename"""
        ext = os.path.splitext(filename)[1].lower()
        if ext in ALLOWED_EXTENSIONS['image']:
            return 'image'
        elif ext in ALLOWED_EXTENSIONS['video']:
            return 'video'
        return None
    
    def add_file(
        self,
        source_path: str,
        name: str = None,
        tags: List[str] = None,
        collection: str = None,
    ) -> Dict:
        """
        Add a file to the media library
        
        Args:
            source_path: Path to the source file
            name: Display name (default: filename)
            tags: Tags for organization
            collection: Collection name
        """
        if not os.path.exists(source_path):
            return {'success': False, 'error': 'File not found'}
        
        # Check file size
        file_size = os.path.getsize(source_path)
        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            return {'success': False, 'error': f'File too large (max {MAX_FILE_SIZE_MB}MB)'}
        
        # Determine media type
        filename = os.path.basename(source_path)
        media_type = self._get_media_type(filename)
        if not media_type:
            return {'success': False, 'error': 'Unsupported file type'}
        
        # Check for duplicates
        file_hash = self._get_file_hash(source_path)
        for existing in self.metadata['files']:
            if existing.get('hash') == file_hash:
                return {'success': False, 'error': 'File already exists in library', 'file_id': existing['id']}
        
        # Generate unique filename
        file_id = f"{media_type}_{int(datetime.now().timestamp() * 1000)}"
        ext = os.path.splitext(filename)[1]
        new_filename = f"{file_id}{ext}"
        
        # Copy to library
        subdir = "images" if media_type == "image" else "videos"
        dest_path = os.path.join(self.media_dir, subdir, new_filename)
        
        try:
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            return {'success': False, 'error': f'Failed to copy file: {e}'}
        
        # Get mime type
        mime_type, _ = mimetypes.guess_type(filename)
        
        # Create metadata entry
        file_entry = {
            'id': file_id,
            'name': name or filename,
            'filename': new_filename,
            'original_name': filename,
            'media_type': media_type,
            'mime_type': mime_type,
            'size_bytes': file_size,
            'hash': file_hash,
            'tags': tags or [],
            'collection': collection,
            'path': dest_path,
            'use_count': 0,
            'created_at': datetime.now().isoformat(),
        }
        
        self.metadata['files'].append(file_entry)
        self.save_metadata()
        
        logger.info(f"Media added: {file_entry['name']} ({file_id})")
        return {'success': True, 'file': file_entry}
    
    def get_file(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID"""
        for f in self.metadata['files']:
            if f['id'] == file_id:
                return f
        return None
    
    def get_file_path(self, file_id: str) -> Optional[str]:
        """Get the actual file path for a media item"""
        file_entry = self.get_file(file_id)
        if file_entry and os.path.exists(file_entry['path']):
            return file_entry['path']
        return None
    
    def update_file(self, file_id: str, updates: Dict) -> bool:
        """Update file metadata"""
        for f in self.metadata['files']:
            if f['id'] == file_id:
                for key, value in updates.items():
                    if key not in ('id', 'filename', 'path', 'hash', 'created_at'):
                        f[key] = value
                self.save_metadata()
                return True
        return False
    
    def delete_file(self, file_id: str) -> bool:
        """Delete a file from the library"""
        file_entry = self.get_file(file_id)
        if not file_entry:
            return False
        
        # Delete actual file
        if os.path.exists(file_entry['path']):
            try:
                os.remove(file_entry['path'])
            except Exception as e:
                logger.warning(f"Could not delete file: {e}")
        
        # Remove from metadata
        self.metadata['files'] = [f for f in self.metadata['files'] if f['id'] != file_id]
        self.save_metadata()
        
        logger.info(f"Media deleted: {file_id}")
        return True
    
    def record_use(self, file_id: str):
        """Record that a file was used in a post"""
        for f in self.metadata['files']:
            if f['id'] == file_id:
                f['use_count'] = f.get('use_count', 0) + 1
                f['last_used'] = datetime.now().isoformat()
                self.save_metadata()
                break
    
    def get_all_files(self, media_type: str = None) -> List[Dict]:
        """Get all files, optionally filtered by type"""
        files = self.metadata['files']
        if media_type:
            files = [f for f in files if f['media_type'] == media_type]
        return sorted(files, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def get_files_by_tag(self, tag: str) -> List[Dict]:
        """Get files with a specific tag"""
        return [f for f in self.metadata['files'] if tag in f.get('tags', [])]
    
    def get_files_by_collection(self, collection: str) -> List[Dict]:
        """Get files in a specific collection"""
        return [f for f in self.metadata['files'] if f.get('collection') == collection]
    
    def search_files(self, query: str) -> List[Dict]:
        """Search files by name or tags"""
        query = query.lower()
        return [
            f for f in self.metadata['files']
            if query in f['name'].lower() or
               any(query in tag.lower() for tag in f.get('tags', []))
        ]
    
    # Collections
    def create_collection(self, name: str, description: str = None) -> Dict:
        """Create a new collection"""
        collection = {
            'name': name,
            'description': description,
            'created_at': datetime.now().isoformat(),
        }
        self.metadata['collections'].append(collection)
        self.save_metadata()
        return {'success': True, 'collection': collection}
    
    def delete_collection(self, name: str) -> bool:
        """Delete a collection (files are not deleted)"""
        original_len = len(self.metadata['collections'])
        self.metadata['collections'] = [c for c in self.metadata['collections'] if c['name'] != name]
        if len(self.metadata['collections']) < original_len:
            # Remove collection reference from files
            for f in self.metadata['files']:
                if f.get('collection') == name:
                    f['collection'] = None
            self.save_metadata()
            return True
        return False
    
    def get_collections(self) -> List[Dict]:
        """Get all collections with file counts"""
        collections = []
        for c in self.metadata['collections']:
            files = self.get_files_by_collection(c['name'])
            collections.append({
                **c,
                'file_count': len(files),
            })
        return collections
    
    def get_stats(self) -> Dict:
        """Get library statistics"""
        files = self.metadata['files']
        images = [f for f in files if f['media_type'] == 'image']
        videos = [f for f in files if f['media_type'] == 'video']
        
        total_size = sum(f.get('size_bytes', 0) for f in files)
        
        return {
            'total_files': len(files),
            'images': len(images),
            'videos': len(videos),
            'collections': len(self.metadata['collections']),
            'total_size_mb': round(total_size / 1024 / 1024, 2),
            'most_used': sorted(files, key=lambda x: x.get('use_count', 0), reverse=True)[:5],
        }


# Global instance
media_library = MediaLibrary() if ENABLE_MEDIA_LIBRARY else None
