import time
import logging
import threading
import requests
from datetime import datetime
from core.database import get_connection
from core.config import get_config
from core.health_server import _state, _start_time

class TelegramListener:
    def __init__(self, bot_token, chat_id, broker_client=None):
        self.bot_token = bot_token
        self.allowed_chat_id = str(chat_id).strip()
        self.broker_client = broker_client
        self.offset = None
        self.running = False
        self.session = requests.Session()

    def start(self):
        """Arranca el bucle de escucha en un hilo daemon secundario."""
        if self.running:
            logging.warning("El escuchador interactivo de Telegram ya está corriendo.")
            return
        
        self.running = True
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        logging.info("Escuchador interactivo de Telegram iniciado en segundo plano (24/7).")

    def _run_loop(self):
        # 1. Limpiar/Omitir mensajes antiguos para no procesar comandos viejos al arrancar
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            res = self.session.get(url, params={"limit": 1, "offset": -1}, timeout=10).json()
            if res.get("ok") and res.get("result"):
                self.offset = res["result"][0]["update_id"] + 1
                logging.info(f"Telegram offset inicializado en {self.offset} para omitir mensajes anteriores.")
        except Exception as e:
            logging.warning(f"No se pudo inicializar el offset de Telegram de inicio: {e}")

        # 2. Bucle principal de Long Polling
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {"timeout": 30}
                if self.offset is not None:
                    params["offset"] = self.offset

                response = self.session.get(url, params=params, timeout=35).json()
                if response.get("ok"):
                    for update in response.get("result", []):
                        self.offset = update["update_id"] + 1
                        message = update.get("message", {})
                        chat = message.get("chat", {})
                        chat_id = str(chat.get("id", "")).strip()
                        text = message.get("text", "").strip()

                        if not text or not chat_id:
                            continue

                        # 🚨 VALIDACIÓN DE SEGURIDAD EXCLUSIVA
                        if chat_id != self.allowed_chat_id:
                            logging.warning(
                                f"Telegram Bloqueado: Mensaje no autorizado de Chat ID {chat_id}. "
                                f"Contenido: '{text[:15]}...'"
                            )
                            continue

                        # Procesar comando válido
                        self._handle_command(chat_id, text)
            except requests.exceptions.RequestException as e:
                logging.debug(f"Error temporal de red en Telegram getUpdates: {e}")
                time.sleep(5)
            except Exception as e:
                logging.error(f"Error crítico en el bucle del Telegram Listener: {e}")
                time.sleep(5)

    def _handle_command(self, chat_id, text):
        command = text.split()[0].lower() if text else ""
        
        if command in ("/start", "/ayuda", "/help"):
            response = (
                "🤖 <b>¡Bienvenido a TradingProSystem Bot!</b>\n\n"
                "Este bot te permite monitorear y consultar tu sistema de trading en tiempo real de forma segura.\n\n"
                "📌 <b>Comandos Disponibles:</b>\n"
                "🔹 <code>/estado</code> - Muestra la salud del sistema y configuraciones activas.\n"
                "🔹 <code>/historial_hoy</code> - Lista las transacciones completadas hoy con su PnL.\n"
                "🔹 <code>/balance</code> o <code>/posiciones</code> - Consulta fondos, poder de compra y posiciones abiertas en Alpaca.\n"
                "🔹 <code>/ayuda</code> - Muestra este menú informativo.\n\n"
                "🔒 <b>Nota de Seguridad:</b> Tu chat está verificado y restringido exclusivamente para tu ID de usuario."
            )
            self.send_reply(chat_id, response)

        elif command == "/estado":
            self._cmd_estado(chat_id)

        elif command == "/historial_hoy":
            self._cmd_historial_hoy(chat_id)

        elif command in ("/balance", "/posiciones"):
            self._cmd_balance_posiciones(chat_id)

        else:
            response = "❓ <b>Comando no reconocido.</b> Escribe <code>/ayuda</code> para ver la lista de comandos disponibles."
            self.send_reply(chat_id, response)

    def _cmd_estado(self, chat_id):
        try:
            config = get_config()
            auto_trade = config.get("auto_trade", False)
            auto_scan = config.get("auto_scan", False)
            
            # Uptime
            uptime_seconds = int(time.time() - _start_time)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"
            
            # Broker Connection
            broker_status = "🔴 Desconectado"
            if self.broker_client and self.broker_client.is_connected():
                broker_status = "🟢 Conectado"
                
            last_scan = _state.get("last_scan")
            last_scan_str = last_scan if last_scan else "Ninguno aún"
            
            response = (
                "🖥️ <b>Estado del Sistema TradingProSystem</b>\n\n"
                f"🤖 <b>Auto-Trade:</b> {'🟢 Encendido (Operando)' if auto_trade else '🔴 Apagado (Simulación/Pausa)'}\n"
                f"🔍 <b>Auto-Scan:</b> {'🟢 Activo' if auto_scan else '🔴 Inactivo'}\n"
                f"💼 <b>Broker Alpaca:</b> {broker_status}\n"
                f"⏰ <b>Uptime del Worker:</b> <code>{uptime_str}</code>\n"
                f"🎯 <b>Último Escaneo:</b> <code>{last_scan_str}</code>\n"
                f"📈 <b>Trades en Sesión:</b> <code>{_state.get('total_trades_session', 0)}</code>"
            )
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error procesando comando /estado: {e}")
            self.send_reply(chat_id, f"❌ Error al consultar el estado del sistema: {str(e)}")

    def _cmd_historial_hoy(self, chat_id):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            hoy = datetime.now().strftime("%Y-%m-%d")
            cursor.execute(
                "SELECT ticker, tipo, precio, cantidad, score, pnl, fecha FROM trades WHERE fecha LIKE ? ORDER BY id DESC",
                (f"{hoy}%",)
            )
            rows = cursor.fetchall()
            
            if not rows:
                self.send_reply(chat_id, f"📭 <b>Historial:</b> No se han registrado operaciones hoy (<code>{hoy}</code>).")
                return
                
            response = f"📊 <b>Historial de operaciones de hoy ({hoy}):</b>\n\n"
            total_pnl = 0.0
            pnl_count = 0
            
            for row in rows:
                ticker, tipo, precio, cantidad, score, pnl, fecha = row
                
                # Formatear PnL
                if pnl is not None:
                    pnl_val = float(pnl)
                    total_pnl += pnl_val
                    pnl_count += 1
                    pnl_str = f"💵 PnL: <b>${pnl_val:+.2f}</b>"
                else:
                    pnl_str = "💵 PnL: <b>N/A (Abierta)</b>"
                    
                emoji = "🟢 LONG (Compra)" if "LONG" in tipo or "buy" in tipo.lower() else "🔴 SHORT (Venta)"
                hora = fecha.split()[1] if " " in fecha else fecha
                
                response += (
                    f"🔹 <b>{ticker}</b> | {emoji} a las <code>{hora}</code>\n"
                    f"  • Precio: <code>${precio:,.2f}</code> | Cant: <code>{cantidad}</code>\n"
                    f"  • Score Estrategia: <code>{score}/100</code>\n"
                    f"  • {pnl_str}\n\n"
                )
                
            if pnl_count > 0:
                response += f"🏁 <b>PnL Acumulado Cerrado Hoy:</b> <code>${total_pnl:+.2f}</code>"
            
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en comando /historial_hoy: {e}")
            self.send_reply(chat_id, f"❌ Error al consultar el historial de hoy: {str(e)}")

    def _cmd_balance_posiciones(self, chat_id):
        try:
            if not self.broker_client or not self.broker_client.is_connected():
                self.send_reply(chat_id, "⚠️ El Broker Alpaca no está configurado o no está conectado.")
                return

            # 1. Consultar balance
            acc = self.broker_client.get_account_info()
            if not acc:
                self.send_reply(chat_id, "❌ No se pudo recuperar la información de la cuenta de Alpaca.")
                return
                
            buying_power = acc.get("buying_power", 0.0)
            equity = acc.get("equity", 0.0)
            status = acc.get("status", "Unknown")
            
            response = (
                "💼 <b>Cartera y Balance en Alpaca</b>\n\n"
                f"💳 <b>Capital Total (Equity):</b> <code>${equity:,.2f}</code>\n"
                f"💵 <b>Poder de Compra:</b> <code>${buying_power:,.2f}</code>\n"
                f"🚦 <b>Estado Cuenta:</b> <code>{status}</code>\n\n"
            )
            
            # 2. Consultar posiciones
            positions = self.broker_client.get_open_positions()
            if not positions:
                response += "📭 <b>Posiciones Abiertas:</b> Ninguna posición activa."
            else:
                response += "📌 <b>Posiciones Activas:</b>\n\n"
                for p in positions:
                    symbol = p.get("symbol")
                    qty = p.get("qty", 0.0)
                    mkt_val = p.get("market_value", 0.0)
                    unrealized_pl = p.get("unrealized_pl", 0.0)
                    unrealized_plpc = p.get("unrealized_plpc", 0.0)
                    side = str(p.get("side", "long")).upper()
                    
                    side_emoji = "🟢" if side == "LONG" else "🔴"
                    pl_emoji = "📈" if unrealized_pl >= 0 else "📉"
                    
                    response += (
                        f"{side_emoji} <b>{symbol}</b> ({side})\n"
                        f"  • Cantidad: <code>{qty}</code> | Valor: <code>${mkt_val:,.2f}</code>\n"
                        f"  • PnL Flotante: {pl_emoji} <b>${unrealized_pl:+.2f}</b> (<code>{unrealized_plpc:+.2f}%</code>)\n\n"
                    )
                    
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en comando /balance: {e}")
            self.send_reply(chat_id, f"❌ Error al consultar la cartera de Alpaca: {str(e)}")

    def send_reply(self, chat_id, text):
        """Envía una respuesta de vuelta al chat en formato HTML."""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            res = self.session.post(url, json=payload, timeout=10)
            if res.status_code != 200:
                logging.error(f"Error enviando respuesta Telegram: {res.text}")
        except Exception as e:
            logging.error(f"Error de red enviando respuesta Telegram: {e}")