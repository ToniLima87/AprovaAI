import sys
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Garante que a raiz do projeto está no PATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import inicializar_banco
from src.api.routes import router as api_router


# Gerencia o ciclo de vida da aplicação (substitui os eventos depreciados de startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa o banco de dados antes de subir o servidor
    inicializar_banco()
    print("🎯 Banco de dados SQLite verificado e inicializado.")
    yield


# Inicializa o app FastAPI
app = FastAPI(
    title="AprovaAI API",
    description="Backend escalável para o agente mentor de concursos de TI usando Google GenAI",
    version="1.0.0",
    lifespan=lifespan
)

# Configuração de CORS (Permite que um frontend se conecte à API sem bloqueios de segurança)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Em produção, define os domínios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui as rotas que desenvolvemos
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    # Roda o servidor Uvicorn na porta 8000
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)