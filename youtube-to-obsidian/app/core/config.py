"""Carrega variáveis de ambiente e expõe Settings tipadas via pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação, populadas via .env ou variáveis de ambiente."""

    obsidian_vault_path: str = "C:/Documentos/Obsidian Vault"
    obsidian_youtube_folder: str = "YouTube"
    default_transcript_language: str = "pt"
    related_videos_count: int = 5
    related_min_similarity: float = 0.10
    topic_tags_count: int = 5
    port: int = 8000
    apify_api_key: str = ""
    anthropic_api_key: str = ""
    database_path: str = "data/oyto_os.db"
    database_url: str = ""
    documents_storage_path: str = "data/documents"

    # Anthropic e RAG Settings
    anthropic_model_default: str = "claude-sonnet-4-6"
    anthropic_model_light: str = "claude-haiku-4-5"
    llm_max_tokens_default: int = 4096
    llm_temperature_default: float = 0.7
    llm_request_timeout_seconds: int = 60

    # Segundo Cérebro RAG
    brain_retrieval_top_k: int = 5
    brain_retrieval_min_similarity: float = 0.05
    brain_chat_history_window: int = 10


    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def youtube_output_dir(self) -> Path:
        """Caminho completo da pasta de saída dentro do vault."""
        return Path(self.obsidian_vault_path) / self.obsidian_youtube_folder


settings = Settings()
