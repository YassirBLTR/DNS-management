import os
from typing import Optional

class Settings:
    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")  # Bind to all interfaces for direct access
    PORT: int = int(os.getenv("PORT", "8003"))
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dns_management.db")
    
    # Alternative database configurations
    @property
    def database_url_with_fallback(self) -> str:
        """Get database URL with PostgreSQL fallback if SQLite3 is not available"""
        db_url = self.DATABASE_URL
        
        # If SQLite is specified but not available, suggest PostgreSQL
        if db_url.startswith("sqlite:"):
            try:
                import sqlite3
                return db_url
            except ImportError:
                print("WARNING: SQLite3 not available. Consider using PostgreSQL:")
                print("DATABASE_URL=postgresql://user:password@localhost/dns_management")
                return db_url
        return db_url
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE", "dns_management.log")
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

settings = Settings()
