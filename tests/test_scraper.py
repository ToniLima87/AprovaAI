"""Testes do scraper de vagas de concursos.

A rede é totalmente mockada: nenhum teste depende de internet nem de chaves de API.
Para rodar:  pytest -v
"""
import pytest

from src.tools import scraper_tools
from src.tools.scraper_tools import buscar_vagas_concurso


class _FakeResponse:
    """Resposta HTTP simulada para substituir requests.get."""

    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def test_retorna_vagas_quando_html_tem_concurso_de_ti(monkeypatch):
    html = """
    <html><body>
        <div class="caixa">
            <a href="https://exemplo.com/serpro">Analista de Sistemas - SERPRO</a>
            Vaga para desenvolvedor na area de tecnologia.
        </div>
    </body></html>
    """
    monkeypatch.setattr(
        scraper_tools.requests, "get", lambda *a, **k: _FakeResponse(200, html)
    )

    resultado = buscar_vagas_concurso("tecnologia da informação")

    assert "Concurso" in resultado
    assert "SERPRO" in resultado
    assert "https://exemplo.com/serpro" in resultado


def test_fallback_ti_quando_sem_resultados(monkeypatch):
    """Sem vagas no HTML + área de TI deve acionar o fallback de contingência."""
    monkeypatch.setattr(
        scraper_tools.requests, "get", lambda *a, **k: _FakeResponse(200, "<html></html>")
    )

    resultado = buscar_vagas_concurso("desenvolvedor")

    assert "SERPRO" in resultado
    assert "DATAPREV" in resultado


def test_fallback_area_desconhecida(monkeypatch):
    """Sem vagas no HTML + área fora de TI deve retornar mensagem de 'nenhum concurso'."""
    monkeypatch.setattr(
        scraper_tools.requests, "get", lambda *a, **k: _FakeResponse(200, "<html></html>")
    )

    resultado = buscar_vagas_concurso("medicina veterinária")

    assert "Nenhum concurso recente mapeado" in resultado
    assert "medicina veterinária" in resultado


def test_fallback_quando_requisicao_lanca_excecao(monkeypatch):
    """Timeout/erro de conexão não pode quebrar o agente: deve cair no fallback."""

    def _raise(*args, **kwargs):
        raise ConnectionError("timeout simulado")

    monkeypatch.setattr(scraper_tools.requests, "get", _raise)

    resultado = buscar_vagas_concurso("tecnologia")

    assert "SERPRO" in resultado
    assert "DATAPREV" in resultado


def test_resultado_sempre_string(monkeypatch):
    monkeypatch.setattr(
        scraper_tools.requests, "get", lambda *a, **k: _FakeResponse(200, "<html></html>")
    )

    assert isinstance(buscar_vagas_concurso("ti"), str)
