"""Configuration management using pydantic-settings"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # OpenAI
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    llm_model: str = "gpt-4o-mini"

    # Cache Configuration
    cache_similarity_threshold: float = 0.95

    # Vector Search Configuration
    vector_search_limit: int = 10

    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    gradio_port: int = 7860

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
