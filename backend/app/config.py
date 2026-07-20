from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "ragdb"
    db_user: str = "postgres"
    db_password: str = "change-me"

    # Ollama LLM (local)
    ollama_base_url: str = "http://localhost:11434"

    # Ollama Cloud
    ollama_api_key: str = ""
    ollama_cloud_base_url: str = "https://ollama.com"
    summarization_model: str = "gemma4:31b"
    generation_model: str = "gemma4:31b"
    summarization_temperature: float = 0.3
    generation_temperature: float = 0.1

    # Embedding (Jina AI)
    jina_api_key: str = ""

    # Demo mode
    demo_mode: bool = False

    # App
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"
    max_concurrency: int = 3
    max_characters: int = 3000
    new_after_n_chars: int = 2500
    combine_text_under_n_chars: int = 500
    min_chunk_size_for_merge: int = 200
    top_k_retrieval: int = 5
    chat_history_depth: int = 6
    upload_dir: str = str(BACKEND_DIR / "data" / "docs")
    image_dir: str = str(BACKEND_DIR / "data" / "images")

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        host = (
            f"[{self.db_host}]" if ":" in self.db_host else self.db_host
        )
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{host}:{self.db_port}/{self.db_name}?ssl=require"
        )


settings = Settings()
