"""
config.py — Centralized environment variable loader.
All settings are read from .env via python-dotenv.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    MONGODB_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/tripwire")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DB_NAME: str = "tripwire"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

    def validate(self):
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in .env")


settings = Settings()
