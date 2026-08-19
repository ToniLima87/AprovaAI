from google import genai
from google.genai import types
from config.settings import settings
from src.database.connection import obter_conexao

# Cliente próprio para geração com grounding (Google Search), separado do chat
# conversacional — o modelo não permite misturar function-calling e google_search
# na mesma requisição.
_cliente = genai.Client(api_key=settings.GEMINI_API_KEY)

# Quantas questões por lote (evita truncamento em respostas muito longas).
_QUESTOES_POR_LOTE = 20
_MAX_QUESTOES = 150

_INSTRUCAO_SIMULADO = """
Você é um especialista em elaboração de provas de concursos de TI.
Gere questões de SIMULADO no estilo da banca informada, baseado no conteúdo programático da vaga.

Regras OBRIGATÓRIAS:
- Pesquise VÁRIAS provas ANTERIORES reais dessa banca para o cargo/área e use-as como referência
  de estilo, nível de dificuldade e temas mais cobrados. Quanto mais provas consultadas, melhor.
- Use múltipla escolha (A a E) OU Certo/Errado, conforme o padrão da banca
  (ex.: CEBRASPE costuma usar Certo/Errado; FGV/FCC usam múltipla escolha).
- Cubra os principais tópicos do conteúdo programático, variando os subtemas entre as questões
  (NÃO repita questões já comuns; traga variedade real).
- FORMATO DE CADA QUESTÃO (siga EXATAMENTE, em Markdown):
  **Questão N**
  <enunciado>
  A) ... / B) ... / C) ... / D) ... / E) ...   (ou "Certo / Errado")

  > ✅ **Gabarito:** <alternativa correta>
  > 💡 **Comentário:** <explicação curta do porquê está correta e, quando útil, por que as outras erram>
  (O gabarito e o comentário DEVEM ficar dentro de um blockquote, cada linha começando com "> ".)
- Numere as questões de forma contínua.
O objetivo é o candidato estudar diretamente pelas respostas comentadas, pois tem pouco tempo.
"""


def _gerar_lote(concurso: str, banca: str, conteudo: str, inicio: int, quantidade: int) -> str:
    prompt = (
        f"{_INSTRUCAO_SIMULADO}\n\n"
        f"Concurso/Cargo: {concurso}\n"
        f"Banca: {banca}\n"
        f"Conteúdo programático: {conteudo}\n\n"
        f"Gere EXATAMENTE {quantidade} questões, numeradas a partir da Questão {inicio}. "
        f"Não escreva introdução nem conclusão: retorne SOMENTE as questões no formato especificado."
    )
    resposta = _cliente.models.generate_content(
        model=settings.MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=8192,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return (resposta.text or "").strip()


def gerar_simulado(concurso: str, banca: str, conteudo_programatico: str,
                   quantidade_questoes: int = 40) -> str:
    """
    Gera um simulado (questões + gabarito comentado) no estilo da banca, baseado em VÁRIAS
    provas anteriores reais (via pesquisa na web) e no conteúdo programático da vaga.
    Gera em lotes para permitir simulados grandes (dezenas a mais de 100 questões).
    Salva o simulado no banco e o retorna em Markdown.

    Args:
        concurso: Nome do concurso/órgão e cargo (ex.: "Prefeitura X - Analista de TI").
        banca: Banca organizadora (ex.: "FGV", "CEBRASPE"). Use "A confirmar" se desconhecida.
        conteudo_programatico: Principais matérias/tópicos da vaga (do edital ou da área).
        quantidade_questoes: Quantas questões gerar (padrão 40; pode chegar a mais de 100).

    Returns:
        O simulado completo em Markdown.
    """
    try:
        alvo = max(5, min(int(quantidade_questoes or 40), _MAX_QUESTOES))
    except (TypeError, ValueError):
        alvo = 40

    partes = []
    feitas = 0
    try:
        while feitas < alvo:
            faltam = min(_QUESTOES_POR_LOTE, alvo - feitas)
            texto_lote = _gerar_lote(concurso, banca, conteudo_programatico, feitas + 1, faltam)
            if not texto_lote:
                break
            partes.append(texto_lote)
            feitas += faltam
    except Exception as e:
        if not partes:
            return f"Erro ao gerar o simulado: {str(e)}"

    if not partes:
        return "Não foi possível gerar o simulado agora."

    cabecalho = (
        f"# 📝 Simulado — {concurso}\n"
        f"**Banca:** {banca}  |  **Questões:** {feitas}\n\n"
        f"> As respostas corretas e os comentários estão destacados em cada questão.\n\n"
        f"---\n\n"
    )
    simulado = cabecalho + "\n\n".join(partes)

    # Persiste o simulado para aparecer na aba "Meus Estudos".
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO simulados (concurso, banca, conteudo) VALUES (?, ?, ?)",
            (concurso[:200], banca[:100], simulado),
        )
        conn.commit()
        conn.close()
        print(f"💾 [Simulado salvo] '{concurso[:60]}' | banca: '{banca}' | {feitas} questões")
    except Exception as e:
        print(f"⚠️ [Falha ao salvar simulado]: {str(e)}")

    return simulado
