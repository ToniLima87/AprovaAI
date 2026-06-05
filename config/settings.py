import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

class Settings:
    PROJECT_NAME: str = "AprovaAI"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    
    # Configurações do Agente
    MODEL_NAME: str = "gemini-2.5-flash" # Modelo rápido e eficiente para lógica
    TEMPERATURE: float = 0.4 # Equilíbrio entre criatividade e precisão técnica
    
    # Caminhos
    DB_NAME: str = "aprova_ai.db"

settings = Settings()