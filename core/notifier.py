import requests
import threading

class TelegramNotifier:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def _send_async(self, text):
        """Envía el mensaje en background sin bloquear el hilo principal (VPS-safe)."""
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                import logging
                logging.error(f"Error enviando notificación Telegram: {resp.text}")
        except Exception:
            pass  # Silencioso — la notificación falló pero no debe tumbar el bot

    def send_message(self, text):
        """
        Envía un mensaje de texto al chat de Telegram sin bloquear el hilo principal.
        Usa un hilo daemon para no retrasar el loop de trading.
        """
        if not self.bot_token or not self.chat_id:
            return
        threading.Thread(target=self._send_async, args=(text,), daemon=True).start()
