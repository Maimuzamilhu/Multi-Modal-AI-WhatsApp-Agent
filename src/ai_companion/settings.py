# settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    GROQ_API_KEY: str | None = None
    ELEVENLABS_API_KEY: str | None = None
    ELEVENLABS_VOICE_ID: str | None = None
    TOGETHER_API_KEY: str | None = None  # ✅ Keep for backward compatibility but not used

    QDRANT_API_KEY: str | None = None
    QDRANT_URL: str | None = None
    QDRANT_PORT: str = "6333"
    QDRANT_HOST: str | None = None
    USE_LOCAL_QDRANT: bool = False

    TEXT_MODEL_NAME: str = "llama-3.3-70b-versatile"
    SMALL_TEXT_MODEL_NAME: str = "llama-3.1-8b-instant"  # ✅ Fixed from gemma2-9b-it
    STT_MODEL_NAME: str = "whisper-large-v3-turbo"
    TTS_MODEL_NAME: str = "eleven_flash_v2_5"
    TTI_MODEL_NAME: str = "pollinations"  
    ITT_MODEL_NAME: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    MEMORY_TOP_K: int = 3
    ROUTER_MESSAGES_TO_ANALYZE: int = 3
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 20
    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5

    SHORT_TERM_MEMORY_DB_PATH: str = "/app/data/memory.db"

settings = Settings()