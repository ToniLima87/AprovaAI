import re
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

URL_PORTAL = "https://www.pciconcursos.com.br/concursos/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Termos que indicam vagas de TI. Tokens curtos (ti) usam fronteira de palavra.
PALAVRAS_TI = [
    "tecnologia da informação", "tecnologia", "informática", "informatica",
    "analista de sistemas", "analista de ti", "desenvolvedor", "desenvolvimento de software",
    "engenharia de software", "sistemas de informação", "ciência da computação",
    "computação", "computacao", "banco de dados", "ciência de dados", "cientista de dados",
    "segurança da informação", "infraestrutura", "redes", "devops", "software",
]

# Bancas organizadoras conhecidas (ordem: termos mais específicos primeiro).
BANCAS_CONHECIDAS = [
    "CEBRASPE", "CESPE", "FGV", "FCC", "Cesgranrio", "VUNESP", "IBFC", "Quadrix",
    "Instituto AOCP", "AOCP", "IADES", "FUNDATEC", "IDECAN", "IBADE", "Consulplan",
    "Avança SP", "Selecon", "Legalle", "Objetiva", "FAFIPA", "FUNDEP", "FUNRIO",
    "Instituto Access", "Instituto Mais", "Avalia", "IGEDUC", "Instituto UniFil",
    "INSTITUTO QUADRIX", "Instituto Consulplan", "Fundação CEFETMINAS", "CEFET",
    "FAURGS", "COMPERVE", "COSEAC", "CEV", "CESPE/CEBRASPE", "GUALIMP", "OMNI",
    "Instituto Avança", "Instituto Verbena", "Instituto CONSULPAM", "CONSULPAM",
    "Reis & Reis", "Klan", "INAZ do Pará", "Instituto Excelência", "FEPESE",
    "EXATUS", "PUBLICONSULT", "SELECON", "Instituto Brasil", "FUMARC", "MS Concursos",
    "Crescer Consultorias", "Conpass", "Itame", "Dédalus", "RBO", "Indep", "VEISS",
]

# Frases que costumam anteceder o nome da banca no texto da notícia.
_PISTAS_BANCA = re.compile(
    r"(?:banca\s+(?:organizadora|examinadora)?|organiza(?:ç|c)[aã]o\s+(?:do|da|fica)"
    r"|organizad[oa]r[ao]\s+(?:do|da|ser[áa])?|respons[áa]vel\s+pela\s+(?:organiza|realiza)"
    r"(?:ç|c)[aã]o|a\s+cargo\s+d[ao]|elaborad[ao]\s+pela|executad[ao]\s+pela"
    r"|sob\s+responsabilidade\s+d[ao])"
    r"[^.;:]{0,40}?\b([A-ZÁÉÍÓÚ][\wÁÉÍÓÚÂÊÔÃÕÇ&.\-]+(?:\s+[A-ZÁÉÍÓÚ0-9&][\wÁÉÍÓÚÂÊÔÃÕÇ&.\-]+){0,4})",
    re.IGNORECASE,
)

# Palavras que NÃO são banca (evita capturar "A Prefeitura", "O Concurso", etc.).
_STOP_NOME_BANCA = {
    "a", "o", "as", "os", "da", "do", "das", "dos", "de", "e", "prefeitura",
    "município", "municipio", "concurso", "certame", "edital", "processo",
    "seleção", "selecao", "comissão", "comissao", "secretaria", "governo",
    "estado", "câmara", "camara", "empresa", "fundação", "fundacao", "será",
    "sera", "ficará", "ficara", "responsável", "responsavel", "organização",
    "organizacao", "banca", "realização", "realizacao",
}

_REGEX_TI = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in PALAVRAS_TI) + r"|ti)\b",
    flags=re.IGNORECASE,
)


def _texto_eh_de_ti(texto: str) -> bool:
    # Fronteira de palavra evita falsos positivos como 'biotecnologia' ou 'partido'.
    return _REGEX_TI.search(texto) is not None


def _limpar_nome_banca(nome: str) -> str:
    """Remove palavras iniciais irrelevantes (artigos, 'Prefeitura', etc.)."""
    tokens = nome.strip().split()
    while tokens and tokens[0].lower() in _STOP_NOME_BANCA:
        tokens.pop(0)
    # remove pontuação solta no fim
    nome_limpo = " ".join(tokens).strip(" .,-")
    return nome_limpo


def _extrair_banca(url: str) -> str:
    """
    Abre a página de detalhe do concurso e tenta identificar a banca
    organizadora a partir do texto do artigo, em duas etapas:
      1) procura nomes de bancas conhecidas;
      2) procura frases como 'banca organizadora ... <Nome>'.
    Retorna o nome da banca ou uma mensagem para confirmar no edital.
    """
    try:
        resposta = requests.get(url, headers=HEADERS, timeout=12)
        if resposta.status_code != 200:
            return "A confirmar (ver edital)"
        soup = BeautifulSoup(resposta.text, "html.parser")
        # Corpo do artigo: parágrafos e itens de lista (evita menus/rodapé).
        corpo = " ".join(
            el.get_text(" ", strip=True) for el in soup.find_all(["p", "li"])
        )

        # Etapa 1: banca conhecida citada em qualquer lugar do corpo.
        for banca in BANCAS_CONHECIDAS:
            if re.search(r"\b" + re.escape(banca) + r"\b", corpo, re.IGNORECASE):
                return banca

        # Etapa 2: captura o nome que segue uma frase-pista (ex.: "banca organizadora será a X").
        melhor = ""
        for m in _PISTAS_BANCA.finditer(corpo):
            candidato = _limpar_nome_banca(m.group(1))
            if 3 <= len(candidato) <= 45 and candidato.lower() not in _STOP_NOME_BANCA:
                melhor = candidato
                break
        if melhor:
            return melhor
    except Exception:
        pass
    return "A confirmar (ver edital)"


def buscar_vagas_concurso(area_interesse: str = "TI") -> str:
    """
    Busca concursos públicos em tempo real no portal PCI Concursos, filtra os
    relacionados à área de Tecnologia da Informação (TI) e, para cada um,
    identifica a banca organizadora consultando a página de detalhe.

    Args:
        area_interesse: Área desejada (ex: "TI", "desenvolvedor", "redes").

    Returns:
        Lista em Markdown com os concursos (órgão, cargo/vagas, salário, banca e link),
        ou uma mensagem honesta caso o portal esteja indisponível.
    """
    try:
        resposta = requests.get(URL_PORTAL, headers=HEADERS, timeout=15)
    except Exception as e:
        return (
            "⚠️ Não consegui acessar o portal de concursos agora "
            f"(erro de conexão: {e}). Tente novamente em alguns instantes."
        )

    if resposta.status_code != 200:
        return (
            "⚠️ O portal de concursos respondeu com status "
            f"{resposta.status_code} e não foi possível ler as vagas agora. "
            "Tente novamente em alguns instantes."
        )

    soup = BeautifulSoup(resposta.text, "html.parser")
    blocos = soup.find_all("div", class_="na")

    if not blocos:
        return (
            "⚠️ O portal foi acessado, mas o formato da página mudou e não consegui "
            "extrair os concursos automaticamente. Avise o desenvolvedor para ajustar o scraper."
        )

    termos_usuario = [t for t in re.split(r"[^a-zà-ú]+", area_interesse.lower()) if len(t) > 2]

    candidatos = []  # vagas de TI (sem banca ainda)
    todos = []       # todos os concursos atuais (fallback honesto)

    for bloco in blocos:
        link_tag = bloco.find("a", href=True)
        if not link_tag:
            continue

        titulo = (link_tag.get("title") or link_tag.get_text(strip=True)).strip()
        orgao = link_tag.get_text(strip=True)
        href = bloco.get("data-url") or link_tag["href"]
        detalhe_tag = bloco.find("div", class_="cd")
        detalhes = detalhe_tag.get_text(" ", strip=True) if detalhe_tag else ""

        todos.append((orgao, titulo, detalhes, href))

        texto_busca = f"{titulo} {orgao} {detalhes}"
        if _texto_eh_de_ti(texto_busca) or any(t in texto_busca.lower() for t in termos_usuario):
            candidatos.append((orgao, titulo, detalhes, href))

    def _formatar(orgao, titulo, detalhes, href, banca=None):
        linhas = [
            f"- **{orgao}**",
            f"  - {titulo}",
            f"  - Vagas/Salário: {detalhes or 'ver edital'}",
        ]
        if banca is not None:
            linhas.append(f"  - Banca organizadora: {banca}")
        linhas.append(f"  - Link: {href}")
        return "\n".join(linhas)

    if candidatos:
        # Lista TODOS os concursos de TI (cap de segurança) e extrai a banca de cada um EM PARALELO.
        selecionados = candidatos[:25]
        with ThreadPoolExecutor(max_workers=8) as executor:
            bancas = list(executor.map(lambda c: _extrair_banca(c[3]), selecionados))

        resultados = [
            _formatar(orgao, titulo, detalhes, href, banca)
            for (orgao, titulo, detalhes, href), banca in zip(selecionados, bancas)
        ]

        cabecalho = (
            f"🔎 Encontrei {len(resultados)} concurso(s) de TI em aberto agora no PCI Concursos "
            "(com a banca organizadora de cada um):\n\n"
        )
        return cabecalho + "\n\n".join(resultados)

    # Sem match de TI: entrega os concursos REAIS abertos no momento, sem inventar nada.
    cabecalho = (
        f"Não encontrei concursos abertos especificamente de '{area_interesse}' neste momento. "
        "Estes são os concursos atualmente em destaque no portal:\n\n"
    )
    return cabecalho + "\n\n".join(_formatar(*c) for c in todos[:8])
