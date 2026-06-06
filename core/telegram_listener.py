import time
import logging
import threading
import requests
from datetime import datetime
from core.database import get_connection, save_price_alert, get_price_alerts, delete_price_alert
from core.config import get_config, save_config
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
        parts = text.strip().split()
        command = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []

        # ── Ayuda / Start ──
        if command in ("/start", "/ayuda", "/help"):
            response = (
                "🤖 <b>¡Bienvenido a TradingProSystem Bot!</b>\n\n"
                "Este bot te permite monitorear y consultar tu sistema de trading en tiempo real de forma segura.\n\n"
                "📌 <b>Comandos de Consulta:</b>\n"
                "🔹 <code>/estado</code> - Salud del sistema y configuraciones activas.\n"
                "🔹 <code>/historial_hoy</code> - Operaciones completadas hoy con su PnL.\n"
                "🔹 <code>/balance</code> o <code>/posiciones</code> - Fondos y posiciones abiertas en Alpaca.\n"
                "🔹 <code>/señal SPY</code> - Score, dirección y escenario de un ticker.\n"
                "🔹 <code>/señales</code> - Top 5 señales de compra y venta del último escaneo.\n\n"
                "💵 <b>Comandos de Capital:</b>\n"
                "🔹 <code>/monto 200</code> - Cambiar monto por operación (USD).\n"
                "🔹 <code>/pnl</code> - PnL acumulado de los últimos 7 días por ticker.\n\n"
                "⚙️ <b>Comandos de Control:</b>\n"
                "🔹 <code>/auto_trade on</code> | <code>off</code> - Activar/Desactivar ejecución automática.\n"
                "🔹 <code>/auto_scan on</code> | <code>off</code> - Activar/Desactivar escaneo de mercado.\n\n"
                "⏰ <b>Alertas de Precio:</b>\n"
                "🔹 <code>/alerta AAPL 200</code> - Crear alerta cuando AAPL supere $200.\n"
                "🔹 <code>/alerta_bajo AAPL 180</code> - Crear alerta cuando AAPL caiga debajo de $180.\n"
                "🔹 <code>/alertas</code> - Listar todas las alertas activas.\n"
                "🔹 <code>/borrar_alerta 3</code> - Eliminar la alerta #3.\n\n"
                "🔒 <b>Nota de Seguridad:</b> Tu chat está restringido exclusivamente para tu ID de usuario."
            )
            self.send_reply(chat_id, response)

        # ── Control de Auto-Trade ──
        elif command == "/auto_trade":
            self._cmd_toggle(chat_id, "auto_trade", args)

        # ── Control de Auto-Scan ──
        elif command == "/auto_scan":
            self._cmd_toggle(chat_id, "auto_scan", args)

        # ── Señal de un ticker ──
        elif command == "/señal":
            self._cmd_senal(chat_id, args)

        # ── Top señales ──
        elif command == "/señales":
            self._cmd_senales(chat_id)

        # ── Estado ──
        elif command == "/estado":
            self._cmd_estado(chat_id)

        # ── Historial ──
        elif command == "/historial_hoy":
            self._cmd_historial_hoy(chat_id)

        # ── Cambiar monto ──
        elif command == "/monto":
            self._cmd_monto(chat_id, args)

        # ── PnL ──
        elif command == "/pnl":
            self._cmd_pnl(chat_id)

        # ── Alertas ──
        elif command == "/alerta":
            self._cmd_alerta(chat_id, args, "ABOVE")
        elif command == "/alerta_bajo":
            self._cmd_alerta(chat_id, args, "BELOW")
        elif command == "/alertas":
            self._cmd_alertas(chat_id)
        elif command == "/borrar_alerta":
            self._cmd_borrar_alerta(chat_id, args)

        # ── Balance / Posiciones ──
        elif command in ("/balance", "/posiciones"):
            self._cmd_balance_posiciones(chat_id)

        else:
            response = "❓ <b>Comando no reconocido.</b> Escribe <code>/ayuda</code> para ver la lista de comandos disponibles."
            self.send_reply(chat_id, response)

    # ═══════════════════════════════════════════════════════════════
    # NUEVO — Comandos de Control
    # ═══════════════════════════════════════════════════════════════

    def _cmd_toggle(self, chat_id, key, args):
        """Activa o desactiva auto_trade o auto_scan."""
        try:
            if not args or args[0].lower() not in ("on", "off"):
                self.send_reply(chat_id, f"⚠️ Uso: <code>/{key} on</code> o <code>/{key} off</code>")
                return

            value = args[0].lower() == "on"
            config = get_config()
            old_value = config.get(key, False)
            config[key] = value
            save_config(config)

            emoji = "🟢" if value else "🔴"
            estado = "ENCENDIDO" if value else "APAGADO"
            self.send_reply(chat_id, f"{emoji} <b>{key.replace('_', '-').title()}: {estado}</b>")
            logging.info(f"📝 [Telegram] {key} cambiado a {value} por comando de usuario.")
        except Exception as e:
            logging.error(f"Error en comando /{key}: {e}")
            self.send_reply(chat_id, f"❌ Error al cambiar {key}: {str(e)}")

    def _cmd_senal(self, chat_id, args):
        """Muestra la señal actual de un ticker específico."""
        try:
            if not args:
                self.send_reply(chat_id, "⚠️ Uso: <code>/señal SPY</code>")
                return

            ticker = args[0].upper().strip()
            self.send_reply(chat_id, f"🔍 Analizando <b>{ticker}</b>...")

            from core.data_fetcher import get_stock_data
            from core.strategy import apply_strategy, get_spy_sentiment

            spy_sent = get_spy_sentiment()
            df = get_stock_data(ticker, period="5d", interval="15m")

            if df.empty or len(df) < 50:
                self.send_reply(chat_id, f"⚠️ No hay suficientes datos para <b>{ticker}</b>.")
                return

            df_a = apply_strategy(df, spy_sentiment=spy_sent, ticker_symbol=ticker)
            latest = df_a.iloc[-1]
            score = int(latest['Score'])
            price = float(latest['Close'])
            scenario = latest.get('Market_Scenario', 'Estándar')
            ml_pred = df_a.attrs.get('ml_prediction', 50)

            if score >= 65:
                direccion = "🟢 COMPRA"
            elif score <= 35:
                direccion = "🔴 VENTA"
            else:
                direccion = "⚪ NEUTRAL"

            response = (
                f"📊 <b>Señal para {ticker}</b>\n\n"
                f"💰 Precio: <code>${price:,.2f}</code>\n"
                f"🎯 Score: <code>{score}/100</code> → {direccion}\n"
                f"🧠 ML: <code>{ml_pred}%</code>\n"
                f"📍 Escenario: {scenario}"
            )
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en comando /señal {args}: {e}")
            self.send_reply(chat_id, f"❌ Error al analizar señal: {str(e)}")

    def _cmd_senales(self, chat_id):
        """Top 5 señales de compra y venta del mercado."""
        try:
            self.send_reply(chat_id, "🔍 Escaneando las mejores señales del mercado...")

            config = get_config()
            tickers_str = config.get("tickers", "SPY, QQQ, AAPL")
            tickers = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]

            import concurrent.futures
            from core.data_fetcher import get_stock_data
            from core.strategy import apply_strategy, get_spy_sentiment

            spy_sent = get_spy_sentiment()

            def _analyze_one(t):
                try:
                    df = get_stock_data(t, period="5d", interval="15m")
                    if df.empty or len(df) < 50:
                        return None
                    da = apply_strategy(df, spy_sentiment=spy_sent, ticker_symbol=t)
                    return {
                        "ticker": t,
                        "score": int(da['Score'].iloc[-1]),
                        "price": float(da['Close'].iloc[-1]),
                    }
                except Exception:
                    return None

            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                futures = {ex.submit(_analyze_one, t): t for t in tickers}
                for f in concurrent.futures.as_completed(futures):
                    r = f.result()
                    if r:
                        results.append(r)

            if not results:
                self.send_reply(chat_id, "⚠️ No se pudieron obtener señales en este momento.")
                return

            # Top compras (score > 50, ordenado descendente)
            compras = sorted([r for r in results if r['score'] > 50], key=lambda x: x['score'], reverse=True)[:5]
            # Top ventas (score < 50, ordenado ascendente)
            ventas = sorted([r for r in results if r['score'] < 50], key=lambda x: x['score'])[:5]

            response = "📊 <b>Top Señales del Mercado</b>\n\n"

            if compras:
                response += "🟢 <b>Mejores Compras:</b>\n"
                for i, r in enumerate(compras, 1):
                    response += f"  {i}. <b>{r['ticker']}</b> — Score <code>{r['score']}</code> | <code>${r['price']:,.2f}</code>\n"
                response += "\n"

            if ventas:
                response += "🔴 <b>Mejores Ventas:</b>\n"
                for i, r in enumerate(ventas, 1):
                    response += f"  {i}. <b>{r['ticker']}</b> — Score <code>{r['score']}</code> | <code>${r['price']:,.2f}</code>\n"
                response += "\n"

            if not compras and not ventas:
                response += "⚪ <b>Mercado neutral:</b> Sin señales claras en este momento.\n"

            response += f"<i>Basado en {len(results)} tickers analizados.</i>"
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en comando /señales: {e}")
            self.send_reply(chat_id, f"❌ Error al escanear señales: {str(e)}")

    # ═══════════════════════════════════════════════════════════════
    # Comandos Existentes
    # ═══════════════════════════════════════════════════════════════

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

    # ═══════════════════════════════════════════════════════════════
    # NUEVO — Comandos de Capital y Alertas (Nivel 2)
    # ═══════════════════════════════════════════════════════════════

    def _cmd_monto(self, chat_id, args):
        """Cambia el monto por operación (trade_amount)."""
        try:
            if not args:
                config = get_config()
                current = config.get("trade_amount", 100)
                self.send_reply(chat_id, f"💵 Monto actual: <b>${current:,.2f}</b> USD por operación.\nUsa <code>/monto 200</code> para cambiarlo.")
                return

            try:
                nuevo_monto = float(args[0])
            except ValueError:
                self.send_reply(chat_id, "⚠️ El monto debe ser un número. Ej: <code>/monto 200</code>")
                return

            if nuevo_monto < 10:
                self.send_reply(chat_id, "⚠️ El monto mínimo es $10 USD.")
                return

            config = get_config()
            old_amount = config.get("trade_amount", 100)
            config["trade_amount"] = nuevo_monto
            save_config(config)

            self.send_reply(chat_id, f"✅ Monto actualizado: <b>${old_amount:,.2f}</b> → <b>${nuevo_monto:,.2f}</b> USD")
            logging.info(f"📝 [Telegram] trade_amount cambiado de ${old_amount} a ${nuevo_monto}")
        except Exception as e:
            logging.error(f"Error en /monto: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_pnl(self, chat_id):
        """PnL acumulado de los últimos 7 días por ticker."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ticker, SUM(pnl) as total_pnl, COUNT(*) as trades FROM trades WHERE pnl IS NOT NULL AND fecha >= date('now', '-7 days') GROUP BY ticker ORDER BY total_pnl DESC LIMIT 15"
            )
            rows = cursor.fetchall()

            if not rows:
                self.send_reply(chat_id, "📭 No hay operaciones cerradas en los últimos 7 días.")
                return

            response = "💰 <b>PnL Acumulado — Últimos 7 Días</b>\n\n"
            total = 0.0
            for ticker, pnl, trades in rows:
                emoji = "📈" if pnl >= 0 else "📉"
                response += f"{emoji} <b>{ticker}</b>: <code>${pnl:+,.2f}</code> ({trades} trades)\n"
                total += pnl

            emoji_total = "🟢" if total >= 0 else "🔴"
            response += f"\n{emoji_total} <b>Total:</b> <code>${total:+,.2f}</code>"
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /pnl: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_alerta(self, chat_id, args, direction):
        """Crea una alerta de precio (ABOVE o BELOW)."""
        try:
            if len(args) < 2:
                ejemplo = "/alerta AAPL 200" if direction == "ABOVE" else "/alerta_bajo AAPL 180"
                self.send_reply(chat_id, f"⚠️ Uso: <code>{ejemplo}</code>")
                return

            ticker = args[0].upper().strip()
            try:
                target = float(args[1])
            except ValueError:
                self.send_reply(chat_id, "⚠️ El precio debe ser un número.")
                return

            if target <= 0:
                self.send_reply(chat_id, "⚠️ El precio debe ser positivo.")
                return

            alert_id = save_price_alert(ticker, target, direction)
            if alert_id > 0:
                direccion_txt = "supere" if direction == "ABOVE" else "caiga debajo de"
                self.send_reply(
                    chat_id,
                    f"✅ <b>Alerta #{alert_id} creada:</b> {ticker} cuando {direccion_txt} <code>${target:,.2f}</code>"
                )
                logging.info(f"📝 [Telegram] Alerta #{alert_id}: {ticker} {direction} ${target}")
            else:
                self.send_reply(chat_id, "❌ No se pudo crear la alerta.")
        except Exception as e:
            logging.error(f"Error en /alerta: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_alertas(self, chat_id):
        """Lista todas las alertas activas."""
        try:
            alerts = get_price_alerts(active_only=True)
            if not alerts:
                self.send_reply(chat_id, "📭 No hay alertas activas.\nCrea una con <code>/alerta AAPL 200</code>")
                return

            response = "⏰ <b>Alertas de Precio Activas</b>\n\n"
            for a in alerts:
                direccion = "supere" if a['direction'] == 'ABOVE' else "caiga debajo de"
                response += (
                    f"🔔 <b>#{a['id']}</b> — {a['ticker']} cuando {direccion} <code>${a['target_price']:,.2f}</code>\n"
                    f"    <i>Creada: {a['created_at']}</i>\n\n"
                )
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /alertas: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_borrar_alerta(self, chat_id, args):
        """Elimina una alerta por ID."""
        try:
            if not args:
                self.send_reply(chat_id, "⚠️ Uso: <code>/borrar_alerta 3</code> (el número es el ID de la alerta)")
                return

            try:
                alert_id = int(args[0])
            except ValueError:
                self.send_reply(chat_id, "⚠️ El ID debe ser un número. Usa <code>/alertas</code> para ver los IDs.")
                return

            if delete_price_alert(alert_id):
                self.send_reply(chat_id, f"🗑️ <b>Alerta #{alert_id} eliminada.</b>")
                logging.info(f"📝 [Telegram] Alerta #{alert_id} desactivada.")
            else:
                self.send_reply(chat_id, f"⚠️ No se encontró la alerta #{alert_id}.")
        except Exception as e:
            logging.error(f"Error en /borrar_alerta: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

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