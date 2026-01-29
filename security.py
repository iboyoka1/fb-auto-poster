"""
Security Module - Password hashing, encryption, JWT tokens
"""
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import json

SECRET_KEY = os.getenv('SECRET_KEY', 'fb-auto-poster-secret-2026-dev-key')
JWT_SECRET = os.getenv('JWT_SECRET', 'fb-auto-poster-jwt-2026-dev-secret')

class PasswordManager:
    """Handle password hashing and verification"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with bcrypt"""
        if not password:
            return None
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against hash"""
        if not password or not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            print(f"Password verification error: {e}")
            return False


class TokenManager:
    """Handle JWT authentication tokens"""
    
    @staticmethod
    def generate_token(user_id: str, expires_in_hours: int = 24) -> str:
        """Generate JWT token"""
        payload = {
            'user_id': user_id,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=expires_in_hours)
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    
    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            return {'error': 'Token expired'}
        except jwt.InvalidTokenError:
            return {'error': 'Invalid token'}
    
    @staticmethod
    def refresh_token(token: str) -> str:
        """Refresh an existing token"""
        decoded = TokenManager.verify_token(token)
        if 'error' not in decoded:
            return TokenManager.generate_token(decoded['user_id'])
        return None


class CredentialEncryption:
    """Encrypt and decrypt sensitive credentials"""
    
    @staticmethod
    def get_cipher():
        """Get Fernet cipher"""
        key = os.getenv('ENCRYPTION_KEY', Fernet.generate_key())
        if isinstance(key, str):
            key = key.encode('utf-8')
        return Fernet(key)
    
    @staticmethod
    def encrypt_credentials(data: dict) -> str:
        """Encrypt credential dictionary"""
        try:
            cipher = CredentialEncryption.get_cipher()
            json_str = json.dumps(data)
            encrypted = cipher.encrypt(json_str.encode('utf-8'))
            return encrypted.decode('utf-8')
        except Exception as e:
            print(f"Encryption error: {e}")
            return None
    
    @staticmethod
    def decrypt_credentials(encrypted_data: str) -> dict:
        """Decrypt credential dictionary"""
        try:
            cipher = CredentialEncryption.get_cipher()
            decrypted = cipher.decrypt(encrypted_data.encode('utf-8'))
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            print(f"Decryption error: {e}")
            return None


class RateLimiter:
    """IP-based rate limiting"""
    
    def __init__(self):
        self.attempts = {}
    
    def is_allowed(self, ip: str, max_attempts: int = 5, window_seconds: int = 60) -> bool:
        """Check if IP is allowed based on rate limit"""
        now = datetime.now().timestamp()
        
        if ip not in self.attempts:
            self.attempts[ip] = []
        
        # Remove old attempts outside window
        self.attempts[ip] = [
            timestamp for timestamp in self.attempts[ip]
            if now - timestamp < window_seconds
        ]
        
        # Check if limit exceeded
        if len(self.attempts[ip]) >= max_attempts:
            return False
        
        # Record new attempt
        self.attempts[ip].append(now)
        return True
    
    def get_attempts(self, ip: str) -> int:
        """Get number of attempts for IP"""
        now = datetime.now().timestamp()
        if ip not in self.attempts:
            return 0
        
        # Clean old attempts
        self.attempts[ip] = [
            timestamp for timestamp in self.attempts[ip]
            if now - timestamp < 60
        ]
        
        return len(self.attempts[ip])
    
    def reset(self, ip: str):
        """Reset attempts for IP"""
        if ip in self.attempts:
            del self.attempts[ip]


# Global instances
password_manager = PasswordManager()
token_manager = TokenManager()
credential_encryption = CredentialEncryption()
rate_limiter = RateLimiter()
