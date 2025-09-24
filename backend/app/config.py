# app/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OLLAMA_MODEL: str = "gemma3:4b"
    MAX_CACHE_SIZE: int = 1000
    CACHE_TTL_SECONDS: int = 3600

settings = Settings()
