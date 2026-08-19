#!/usr/bin/env bash
# Sobe o AprovaAI completo: backend (FastAPI:8000) + frontend (Vite:5173).
# Uso: ./start.sh
# Pressione Ctrl+C para encerrar os dois ao mesmo tempo.
set -e

cd "$(dirname "$0")"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "Encerrando AprovaAI..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  pkill -f "uvicorn src.main:app" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# Encerra instâncias antigas do backend
pkill -f "uvicorn src.main:app" 2>/dev/null || true

echo "Iniciando backend (http://localhost:8000)..."
./venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "Iniciando frontend (http://localhost:5173)..."
( cd aprova-ai-web && npm run dev ) &
FRONTEND_PID=$!

echo ""
echo "AprovaAI rodando!"
echo "  - Frontend: http://localhost:5173"
echo "  - Backend:  http://localhost:8000"
echo "  (Ctrl+C para encerrar tudo)"

# Mantém o script vivo enquanto os processos rodam
wait
