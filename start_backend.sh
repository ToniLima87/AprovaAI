#!/usr/bin/env bash
# Sobe o backend FastAPI do AprovaAI na porta 8000.
# Uso: ./start_backend.sh
set -e

cd "$(dirname "$0")"

# Encerra qualquer instância antiga do backend
pkill -f "uvicorn src.main:app" 2>/dev/null || true

exec ./venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
