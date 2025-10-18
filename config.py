"""Pydantic Settings configuration"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str
    ENVIRONMENT: str 
    DEBUG: bool

    # Server
    HOST: str
    PORT: int
    SUPABASE_URL: str
    SUPABASE_API_KEY: str
    # CORS
    ALLOWED_ORIGINS: List[str]

    # API Keys
    GROQ_API_KEY: str
    OPENAI_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


settings = Settings()
