#!/usr/bin/env bash
# Inicia o servidor de desenvolvimento do youtube-to-obsidian
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ativa venv se existir
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Carrega a porta do .env ou usa 8000
PORT=${PORT:-8000}
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep PORT | xargs 2>/dev/null) || true
fi

echo "🚀 Iniciando youtube-to-obsidian em http://localhost:${PORT}"
uvicorn app.main:app --reload --port "${PORT}" --host 0.0.0.0
