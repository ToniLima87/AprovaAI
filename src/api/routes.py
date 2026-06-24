import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.agents.mentor_agent import aprova_ai
from src.database.connection import obter_conexao

router = APIRouter()

# Bancas reconhecidas pelo agente (ordem importa: termos mais específicos primeiro)
BANCAS_CONHECIDAS = [
    "CEBRASPE", "CESPE", "FGV", "FCC", "Cesgranrio", "VUNESP",
    "IBFC", "Quadrix", "AOCP", "IADES", "FUNDATEC", "IDECAN",
]

# Títulos genéricos que NÃO servem como nome de concurso
TITULOS_GENERICOS = {
    "cronograma", "cronograma de estudos", "cronograma estratégico",
    "plano de estudos", "plano tático", "plano de estudo",
}


def _detectar_banca(texto: str) -> str:
    """Identifica a banca citada na resposta do agente."""
    texto_lower = texto.lower()
    for banca in BANCAS_CONHECIDAS:
        if banca.lower() in texto_lower:
            return banca
    return "Não especificada"


def _detectar_concurso(resposta: str, mensagem_usuario: str) -> str:
    """
    Tenta extrair o nome do concurso a partir do primeiro título Markdown
    relevante da resposta; se não houver, usa a mensagem do usuário.
    """
    for linha in resposta.splitlines():
        titulo = linha.strip().lstrip("#").strip()
        # remove ênfase markdown (**, *) das bordas
        titulo_limpo = re.sub(r"[*_`]", "", titulo).strip()
        if (
            linha.strip().startswith("#")
            and titulo_limpo
            and titulo_limpo.lower() not in TITULOS_GENERICOS
        ):
            return titulo_limpo[:120]

    msg = mensagem_usuario.strip()
    return msg[:120] if msg else "Concurso não identificado"

# --- SCHEMAS DE VALIDAÇÃO (PYDANTIC) ---
class PerguntaRequest(BaseModel):
    mensagem: str

class PlanoEstudoSaveRequest(BaseModel):
    concurso: str
    banca: str
    cronograma: str

# --- ENDPOINTS ---

@router.post("/chat", summary="Interagir com o AprovaAI")
async def interagir_com_agente(request: PerguntaRequest):
    """
    Envia uma mensagem para o agente. Se o usuário pedir vagas,
    o agente usará a ferramenta de Scraping automaticamente.
    Se o agente gerar um plano tático, ele salva automaticamente no banco.
    """
    if not request.mensagem.strip():
        raise HTTPException(status_code=400, detail="A mensagem não pode estar vazia.")
    
    # O agente processa a mensagem e decide se executa o Tool Calling
    resposta_agente = aprova_ai.responder(request.mensagem)
    
    # --- AUTOSAVE INTELIGENTE ---
    # Se a resposta contiver indícios de que é um cronograma/plano gerado, salvamos direto
    palavras_chave = ["cronograma", "plano de estudos", "semana 1", "banca"]
    if any(chave in resposta_agente.lower() for chave in palavras_chave) and len(resposta_agente) > 300:
        try:
            concurso = _detectar_concurso(resposta_agente, request.mensagem)
            banca = _detectar_banca(resposta_agente)
            conn = obter_conexao()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO planos_estudo (concurso, banca, cronograma) VALUES (?, ?, ?)",
                (concurso, banca, resposta_agente)
            )
            conn.commit()
            conn.close()
            print(f"💾 [Autosave] Plano guardado — concurso: '{concurso}' | banca: '{banca}'")
        except Exception as e:
            # Mantemos o print para log, mas não travamos a resposta do usuário se o banco falhar
            print(f"⚠️ [Autosave falhou]: {str(e)}")

    return {"resposta": resposta_agente}

@router.post("/plano/salvar", summary="Salvar um plano de estudos no banco")
async def salvar_plano(request: PlanoEstudoSaveRequest):
    """
    Persiste o plano de estudos gerado em Markdown dentro do banco SQLite.
    """
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO planos_estudo (concurso, banca, cronograma) VALUES (?, ?, ?)",
            (request.concurso, request.banca, request.cronograma)
        )
        conn.commit()
        conn.close()
        return {"status": "sucesso", "mensagem": "Plano de estudos guardado com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {str(e)}")

@router.get("/planos", summary="Listar todos os planos salvos")
async def listar_planos():
    """
    Retorna o histórico de todos os planos de estudo guardados pelo usuário.
    """
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("SELECT id, concurso, banca, cronograma, criado_em FROM planos_estudo ORDER BY criado_em DESC")
        rows = cursor.fetchall()
        conn.close()
        
        planos = []
        for row in rows:
            planos.append({
                "id": row[0],
                "concurso": row[1],
                "banca": row[2],
                "cronograma": row[3],
                "criado_em": row[4]
            })
        return {"planos": planos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))