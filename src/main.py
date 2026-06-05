import sys
import os

# Garante que a raiz do projeto está no PATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.mentor_agent import aprova_ai
from src.database.connection import inicializar_banco, obter_conexao

def salvar_plano_no_banco(concurso, banca, cronograma):
    """Salva o histórico do cronograma no banco de dados local."""
    try:
        conn = obter_conexao()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO planos_estudo (concurso, banca, cronograma) VALUES (?, ?, ?)",
            (concurso, banca, cronograma)
        )
        conn.commit()
        conn.close()
        print("\n💾 [Sistema] Plano de estudos salvo com sucesso no banco de dados!")
    except Exception as e:
        print(f"\n❌ Erro ao salvar no banco: {e}")

def rodar_aprova_ai():
    # 1. Inicializa o banco de dados local
    inicializar_banco()
    
    print("="*50)
    print("        🤖 BEM-VINDO AO APROVAAI AGENT 🤖        ")
    print("="*50)
    print("Seu mentor de estudos inteligente para concursos de TI.\n")
    print("Exemplo de comando: 'Quero ver vagas de concurso para desenvolvedor'")
    print("Digite 'sair' para encerrar.\n")
    
    ultima_resposta_agente = ""
    
    while True:
        try:
            user_input = input("Você 👤: ")
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("\nAté logo, Toni! Bons estudos e rumo à aprovação! 🚀")
                break
            
            if not user_input.strip():
                continue
                
            # Chama o agente para processar
            print("\nPensando... 🧠")
            resposta = aprova_ai.responder(user_input)
            ultima_resposta_agente = resposta
            
            print(f"\nAprovaAI 🤖:\n{resposta}\n")
            print("-" * 50)
            
            # Atalho intermediário: se o agente gerou uma tabela markdown, oferece salvamento
            if "|" in resposta and "Semana" in resposta and "Dia" in resposta:
                opcao = input("Deseja salvar este plano de estudos gerado? (s/n): ")
                if opcao.lower() == 's':
                    # Aqui você pode extrair dinamicamente ou pedir os dados pro usuário
                    concurso_nome = input("Digite o nome do Concurso (ex: SERPRO): ")
                    banca_nome = input("Digite a Banca (ex: CEBRASPE): ")
                    salvar_plano_no_banco(concurso_nome, banca_nome, ultima_resposta_agente)
                    print("-" * 50)
                    
        except KeyboardInterrupt:
            print("\nEncerrando o AprovaAI...")
            break

if __name__ == "__main__":
    rodar_aprova_ai()