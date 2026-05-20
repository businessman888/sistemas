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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def youtube_output_dir(self) -> Path:
        """Caminho completo da pasta de saída dentro do vault."""
        return Path(self.obsidian_vault_path) / self.obsidian_youtube_folder


settings = Settings()
