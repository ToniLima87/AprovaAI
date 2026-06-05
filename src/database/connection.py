import sqlite3
from config.settings import settings

def obter_conexao():
    """Retorna uma conexão ativa com o banco SQLite."""
    conn = sqlite3.connect(settings.DB_NAME)
    return conn

def inicializar_banco():
    """Cria as tabelas necessárias caso elas não existam."""
    conn = obter_conexao()
    cursor = conn.cursor()
    
    # Tabela para salvar os cronogramas gerados pelo AprovaAI
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS planos_estudo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concurso TEXT NOT NULL,
            banca TEXT NOT NULL,
            cronograma TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()