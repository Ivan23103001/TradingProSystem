import requests

class TelegramNotifier:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send_message(self, text):
        """
        Envía un mensaje de texto al chat de Telegram usando el bot.
        """
        if not self.bot_token or not self.chat_id:
            return False, "Faltan credenciales de Telegram."

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True, "Notificación enviada con éxito."
            else:
                return False, f"Error del servidor Telegram: {response.text}"
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"
