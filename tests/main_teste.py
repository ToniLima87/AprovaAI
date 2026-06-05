from src.agents.mentor_agent import aprova_ai

def menu_teste():
    print("--- Testando o Cérebro do AprovaAI ---")
    print("Dica: Peça uma sugestão de como estudar para a FGV em TI.\n")
    
    while True:
        user_input = input("Você: ")
        if user_input.lower() in ["sair", "exit", "quit"]:
            break
            
        resposta = aprova_ai.responder(user_input)
        print(f"\nAprovaAI: {resposta}\n")

if __name__ == "__main__":
    menu_teste()