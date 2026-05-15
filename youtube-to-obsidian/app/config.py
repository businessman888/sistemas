"""Carrega variáveis de ambiente e expõe Settings tipadas via pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configurações da aplicação, populadas via .env ou variáveis de ambiente."""

    obsidian_vault_path: str = "C:/Documentos/Obsidian Vault"
    obsidian_youtube_folder: str = "YouTube"
    default_transcript_language: str = "pt"
    port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @property
    def youtube_output_dir(self) -> Path:
        """Caminho completo da pasta de saída dentro do vault."""
        return Path(self.obsidian_vault_path) / self.obsidian_youtube_folder


settings = Settings()
