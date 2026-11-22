from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os

# Do not accept the historical shared/default key for signing or verification.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
_UNSAFE_KEYS = {
    "",
    "your-secret-key-change-in-production",
    "change-me",
    "changeme",
    "secret",
    "test",
}


def _signing_key() -> str:
    if SECRET_KEY.lower() in _UNSAFE_KEYS or len(SECRET_KEY) < 32:
        raise RuntimeError("Strong SECRET_KEY configuration is required for authentication")
    return SECRET_KEY
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, _signing_key(), algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, _signing_key(), algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, _signing_key(), algorithms=[ALGORITHM])
        return payload
    except (JWTError, RuntimeError):
        return None