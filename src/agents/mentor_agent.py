from google import genai
from google.genai import types
from config.settings import settings
from .prompts import SYSTEM_INSTRUCTION
from src.tools.scraper_tools import buscar_vagas_concurso
from src.tools.simulado_tools import gerar_simulado

class AprovaAIAgent:
    def __init__(self):
        # Inicializa o cliente do Google GenAI
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = settings.MODEL_NAME
        
        # Configuração do comportamento do modelo
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=settings.TEMPERATURE,
            tools=[buscar_vagas_concurso, gerar_simulado],  # Vagas em tempo real + geração de simulado
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
        
        # Iniciamos o chat com histórico vazio
        self.chat = self.client.chats.create(model=self.model_id, config=self.config)

    def responder(self, mensagem_usuario: str, anexos: list | None = None):
        """
        Envia a mensagem para o Gemini e retorna a resposta processada.

        Args:
            mensagem_usuario: Texto enviado pelo usuário.
            anexos: Lista opcional de dicts {"data": bytes, "mime_type": str}
                    (ex.: editais em PDF ou imagens) que serão enviados ao modelo.
        """
        try:
            if anexos:
                partes = [types.Part.from_bytes(data=a["data"], mime_type=a["mime_type"]) for a in anexos]
                # O texto vem por último para o modelo considerar os anexos como contexto.
                partes.append(mensagem_usuario or "Analise o(s) arquivo(s) anexado(s).")
                response = self.chat.send_message(partes)
            else:
                response = self.chat.send_message(mensagem_usuario)
            return response.text
        except Exception as e:
            return f"Erro ao processar solicitação: {str(e)}"

    def responder_stream(self, mensagem_usuario: str, anexos: list | None = None):
        """
        Versão em streaming de `responder`: produz a resposta em pedaços (tokens)
        conforme o modelo gera, melhorando muito a sensação de velocidade.

        Yields:
            Pedaços de texto (str) da resposta.
        """
        try:
            if anexos:
                partes = [types.Part.from_bytes(data=a["data"], mime_type=a["mime_type"]) for a in anexos]
                partes.append(mensagem_usuario or "Analise o(s) arquivo(s) anexado(s).")
                fluxo = self.chat.send_message_stream(partes)
            else:
                fluxo = self.chat.send_message_stream(mensagem_usuario)

            for parte in fluxo:
                if getattr(parte, "text", None):
                    yield parte.text
        except Exception as e:
            yield f"Erro ao processar solicitação: {str(e)}"

# Instância global para teste
aprova_ai = AprovaAIAgent()