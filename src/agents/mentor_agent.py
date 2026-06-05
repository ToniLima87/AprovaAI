from google import genai
from google.genai import types
from config.settings import settings
from .prompts import SYSTEM_INSTRUCTION

class AprovaAIAgent:
    def __init__(self):
        # Inicializa o cliente do Google GenAI
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = settings.MODEL_NAME
        
        # Configuração do comportamento do modelo
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=settings.TEMPERATURE,
            tools=[], # As ferramentas (Scraper, etc) serão adicionadas aqui depois
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
        
        # Iniciamos o chat com histórico vazio
        self.chat = self.client.chats.create(model=self.model_id, config=self.config)

    def responder(self, mensagem_usuario: str):
        """
        Envia a mensagem para o Gemini e retorna a resposta processada.
        """
        try:
            response = self.chat.send_message(mensagem_usuario)
            return response.text
        except Exception as e:
            return f"Erro ao processar solicitação: {str(e)}"

# Instância global para teste
aprova_ai = AprovaAIAgent()