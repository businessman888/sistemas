"""FastAPI app: monta rotas, serve arquivos estáticos e configura logging."""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.database import init_db
from app.modules.youtube.routes import router as videos_router
from app.modules.social_media.routes import router as social_media_router
from app.modules.clone.routes import router as clone_router
from app.modules.orchestrator.routes import router as orchestrator_router

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
    title="Oyto OS",
    description="Sistema operacional modular para conexões de conhecimento e análises.",
    version="1.1.0",
)

# --- Eventos de ciclo de vida ---
@app.on_event("startup")
def on_startup():
    init_db()

# --- Rotas da API ---
app.include_router(videos_router)
app.include_router(social_media_router)
app.include_router(clone_router)
app.include_router(orchestrator_router)



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
