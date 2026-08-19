import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.agents.mentor_agent import aprova_ai
from src.database.connection import obter_conexao

# Tipos de anexo aceitos pelo agente (editais em PDF e imagens).
MIMES_PERMITIDOS = {
    "application/pdf",
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
}
TAMANHO_MAX_ARQUIVO = 15 * 1024 * 1024  # 15 MB por arquivo

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


def _parece_plano_de_estudo(resposta: str) -> bool:
    """
    Decide se a resposta é realmente um plano/cronograma de estudos (e não, por
    exemplo, uma listagem de vagas). Exige indícios fortes para evitar salvar lixo.
    """
    if len(resposta) < 300:
        return False

    texto = resposta.lower()

    # Exclui o que é claramente listagem de vagas vinda do scraper
    if "pciconcursos.com.br" in texto or texto.count("link:") >= 2:
        return False

    menciona_plano = "cronograma" in texto or "plano de estudo" in texto
    tem_semanas = len(re.findall(r"semana\s*\d+", texto)) >= 2
    tem_tabela = resposta.count("|") >= 6  # tabela Markdown de cronograma

    return menciona_plano and (tem_semanas or tem_tabela)


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

def _autosalvar_se_plano(resposta_agente: str, mensagem: str) -> None:
    """Salva a resposta no banco apenas se ela for realmente um plano de estudos."""
    if not _parece_plano_de_estudo(resposta_agente):
        return
    try:
        concurso = _detectar_concurso(resposta_agente, mensagem)
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


def _gerar_resposta_e_autosalvar(mensagem: str, anexos: Optional[list] = None) -> str:
    """Aciona o agente e salva automaticamente a resposta se for um plano de estudos."""
    resposta_agente = aprova_ai.responder(mensagem, anexos=anexos)
    _autosalvar_se_plano(resposta_agente, mensagem)
    return resposta_agente


def _stream_resposta(mensagem: str, anexos: Optional[list] = None):
    """Gera a resposta do agente em streaming e faz o autosave ao final."""
    partes = []
    for pedaco in aprova_ai.responder_stream(mensagem, anexos=anexos):
        partes.append(pedaco)
        yield pedaco
    _autosalvar_se_plano("".join(partes), mensagem)


@router.post("/chat", summary="Interagir com o AprovaAI")
async def interagir_com_agente(request: PerguntaRequest):
    """
    Envia uma mensagem (texto) para o agente. Se o usuário pedir vagas,
    o agente usará a ferramenta de Scraping automaticamente.
    Se o agente gerar um plano tático, ele salva automaticamente no banco.
    """
    if not request.mensagem.strip():
        raise HTTPException(status_code=400, detail="A mensagem não pode estar vazia.")

    resposta = _gerar_resposta_e_autosalvar(request.mensagem)
    return {"resposta": resposta}


@router.post("/chat-arquivo", summary="Interagir com o AprovaAI enviando arquivos")
async def interagir_com_arquivos(
    mensagem: str = Form(""),
    arquivos: List[UploadFile] = File(default=[]),
):
    """
    Versão do chat que aceita anexos (editais em PDF ou imagens) junto com a mensagem.
    Os arquivos são enviados ao Gemini como contexto para análise.
    """
    if not mensagem.strip() and not arquivos:
        raise HTTPException(status_code=400, detail="Envie uma mensagem ou ao menos um arquivo.")

    anexos = []
    for arquivo in arquivos:
        if arquivo.content_type not in MIMES_PERMITIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de arquivo não suportado: {arquivo.filename} ({arquivo.content_type}). "
                       "Aceitos: PDF, PNG, JPG, WEBP, GIF.",
            )
        conteudo = await arquivo.read()
        if len(conteudo) > TAMANHO_MAX_ARQUIVO:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo '{arquivo.filename}' excede o limite de 15 MB.",
            )
        anexos.append({"data": conteudo, "mime_type": arquivo.content_type})

    resposta = _gerar_resposta_e_autosalvar(mensagem, anexos=anexos)
    return {"resposta": resposta}


@router.post("/chat-stream", summary="Chat em streaming (texto)")
async def interagir_stream(request: PerguntaRequest):
    """Mesma lógica do /chat, mas a resposta é transmitida em tempo real (streaming)."""
    if not request.mensagem.strip():
        raise HTTPException(status_code=400, detail="A mensagem não pode estar vazia.")
    return StreamingResponse(
        _stream_resposta(request.mensagem),
        media_type="text/plain; charset=utf-8",
    )


@router.post("/chat-arquivo-stream", summary="Chat em streaming com arquivos")
async def interagir_arquivos_stream(
    mensagem: str = Form(""),
    arquivos: List[UploadFile] = File(default=[]),
):
    """Versão em streaming do chat com anexos (editais em PDF ou imagens)."""
    if not mensagem.strip() and not arquivos:
        raise HTTPException(status_code=400, detail="Envie uma mensagem ou ao menos um arquivo.")

    anexos = []
    for arquivo in arquivos:
        if arquivo.content_type not in MIMES_PERMITIDOS:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de arquivo não suportado: {arquivo.filename} ({arquivo.content_type}). "
                       "Aceitos: PDF, PNG, JPG, WEBP, GIF.",
            )
        conteudo = await arquivo.read()
        if len(conteudo) > TAMANHO_MAX_ARQUIVO:
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo '{arquivo.filename}' excede o limite de 15 MB.",
            )
        anexos.append({"data": conteudo, "mime_type": arquivo.content_type})

    return StreamingResponse(
        _stream_resposta(mensagem, anexos=anexos),
        media_type="text/plain; charset=utf-8",
    )

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


@router.delete("/planos/{plano_id}", summary="Apagar um plano de estudos")
async def apagar_plano(plano_id: int):
    """Remove um plano de estudos específico do histórico."""
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM planos_estudo WHERE id = ?", (plano_id,))
        conn.commit()
        removidos = cursor.rowcount
        conn.close()
        if removidos == 0:
            raise HTTPException(status_code=404, detail="Plano não encontrado.")
        return {"status": "sucesso", "removidos": removidos}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/planos", summary="Apagar TODOS os planos de estudo")
async def apagar_todos_planos():
    """Limpa todo o histórico de planos de estudo."""
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM planos_estudo")
        conn.commit()
        removidos = cursor.rowcount
        conn.close()
        return {"status": "sucesso", "removidos": removidos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/simulados", summary="Listar todos os simulados salvos")
async def listar_simulados():
    """Retorna o histórico de simulados (questões + gabarito comentado) gerados."""
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("SELECT id, concurso, banca, conteudo, criado_em FROM simulados ORDER BY criado_em DESC")
        rows = cursor.fetchall()
        conn.close()

        simulados = [
            {
                "id": row[0],
                "concurso": row[1],
                "banca": row[2],
                "conteudo": row[3],
                "criado_em": row[4],
            }
            for row in rows
        ]
        return {"simulados": simulados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/simulados/{simulado_id}", summary="Apagar um simulado")
async def apagar_simulado(simulado_id: int):
    """Remove um simulado específico do histórico."""
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM simulados WHERE id = ?", (simulado_id,))
        conn.commit()
        removidos = cursor.rowcount
        conn.close()
        if removidos == 0:
            raise HTTPException(status_code=404, detail="Simulado não encontrado.")
        return {"status": "sucesso", "removidos": removidos}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/simulados", summary="Apagar TODOS os simulados")
async def apagar_todos_simulados():
    """Limpa todo o histórico de simulados."""
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM simulados")
        conn.commit()
        removidos = cursor.rowcount
        conn.close()
        return {"status": "sucesso", "removidos": removidos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))