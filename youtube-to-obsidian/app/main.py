"""FastAPI app: monta rotas, serve arquivos estáticos e configura logging."""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.modules.youtube.routes import router as videos_router

# --- Logging estruturado ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("youtube-to-obsidian")

# --- FastAPI app ---
app = FastAPI(
    title="YouTube to Obsidian",
    description="Importa transcrições de vídeos do YouTube como markdown para o vault do Obsidian.",
    version="1.0.0",
)

# --- Rotas da API ---
app.include_router(videos_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check simples."""
    return {"status": "ok"}


# --- Arquivos estáticos ---
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve a página principal."""
    index_path = static_dir / "index.html"
    return FileResponse(str(index_path))
