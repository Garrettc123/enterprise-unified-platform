from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # Application
    APP_NAME: str = "Enterprise Unified Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://enterprise_user:enterprise_pass@localhost:5432/enterprise_platform"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://enterprise-unified-platform.vercel.app"
    ]
    
    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    MAX_CONNECTIONS_PER_IP: int = 100
    RATE_LIMIT_PER_MINUTE: int = 1000
    
    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    LOG_LEVEL: str = "INFO"
    
    # Email / SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    EMAIL_FROM_ADDRESS: str = os.getenv("EMAIL_FROM_ADDRESS", "noreply@enterprise-platform.com")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "Enterprise Unified Platform")
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()