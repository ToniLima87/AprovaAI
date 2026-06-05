"""Testes da camada de banco de dados (SQLite).

Usa um arquivo temporário isolado, sem tocar no banco real do projeto.
"""
import sqlite3

import pytest

from config.settings import settings
from src.database import connection
from src.database.connection import inicializar_banco, obter_conexao


@pytest.fixture
def banco_temporario(tmp_path, monkeypatch):
    """Aponta o DB_NAME para um arquivo temporário durante o teste."""
    db_file = tmp_path / "teste.db"
    monkeypatch.setattr(settings, "DB_NAME", str(db_file))
    # `connection` lê settings.DB_NAME em tempo de execução, então o patch acima já basta
    yield str(db_file)


def test_inicializar_banco_cria_tabela(banco_temporario):
    inicializar_banco()

    conn = sqlite3.connect(banco_temporario)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='planos_estudo'"
    )
    tabela = cursor.fetchone()
    conn.close()

    assert tabela is not None
    assert tabela[0] == "planos_estudo"


def test_inserir_e_recuperar_plano(banco_temporario):
    inicializar_banco()

    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO planos_estudo (concurso, banca, cronograma) VALUES (?, ?, ?)",
        ("SERPRO", "CEBRASPE", "| Semana | Dia | Conteúdo |"),
    )
    conn.commit()

    cursor.execute("SELECT concurso, banca FROM planos_estudo WHERE concurso = 'SERPRO'")
    linha = cursor.fetchone()
    conn.close()

    assert linha == ("SERPRO", "CEBRASPE")


def test_inicializar_banco_e_idempotente(banco_temporario):
    """Chamar duas vezes não deve gerar erro (CREATE TABLE IF NOT EXISTS)."""
    inicializar_banco()
    inicializar_banco()  # não deve lançar exceção


def test_obter_conexao_retorna_conexao_valida(banco_temporario):
    conn = obter_conexao()
    assert isinstance(conn, sqlite3.Connection)
    conn.close()
