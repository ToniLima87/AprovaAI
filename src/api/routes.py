from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.agents.mentor_agent import aprova_ai
from src.database.connection import obter_conexao

router = APIRouter()

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
            conn = obter_conexao()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO planos_estudo (concurso, banca, cronograma) VALUES (?, ?, ?)",
                ("Banco do Brasil - TI (Auto)", "Cesgranrio", resposta_agente)
            )
            conn.commit()
            conn.close()
            print("💾 [Autosave] Um novo plano de estudos longo foi guardado automaticamente no banco!")
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