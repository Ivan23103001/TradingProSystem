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
                "🔹 <code>/señales</code> - Top 5 señales de compra y venta del último escaneo.\n"
                "🔹 <code>/chart SPY</code> - Enviar gráfico de velas con EMAs y volumen.\n\n"
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

        # ── Gráfico rápido ──
        elif command == "/chart":
            self._cmd_chart(chat_id, args)

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
    # Comandos de Control (Nivel 1)
    # ═══════════════════════════════════════════════════════════════

    def _cmd_toggle(self, chat_id, key, args):
        """Activa o desactiva auto_trade o auto_scan."""
        try:
            if not args or args[0].lower() not in ("on", "off"):
                self.send_reply(chat_id, f"⚠️ Uso: <code>/{key} on</code> o <code>/{key} off</code>")
                return

            value = args[0].lower() == "on"
            config = get_config()
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
                    return {"ticker": t, "score": int(da['Score'].iloc[-1]), "price": float(da['Close'].iloc[-1])}
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

            compras = sorted([r for r in results if r['score'] > 50], key=lambda x: x['score'], reverse=True)[:5]
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
    # Comandos de Consulta (Existentes)
    # ═══════════════════════════════════════════════════════════════

    def _cmd_estado(self, chat_id):
        try:
            config = get_config()
            uptime_seconds = int(time.time() - _start_time)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"

            broker_status = "🔴 Desconectado"
            if self.broker_client and self.broker_client.is_connected():
                broker_status = "🟢 Conectado"

            last_scan = _state.get("last_scan")
            last_scan_str = last_scan if last_scan else "Ninguno aún"

            response = (
                "🖥️ <b>Estado del Sistema TradingProSystem</b>\n\n"
                f"🤖 <b>Auto-Trade:</b> {'🟢 Encendido' if config.get('auto_trade') else '🔴 Apagado'}\n"
                f"🔍 <b>Auto-Scan:</b> {'🟢 Activo' if config.get('auto_scan') else '🔴 Inactivo'}\n"
                f"💼 <b>Broker Alpaca:</b> {broker_status}\n"
                f"⏰ <b>Uptime del Worker:</b> <code>{uptime_str}</code>\n"
                f"🎯 <b>Último Escaneo:</b> <code>{last_scan_str}</code>\n"
                f"📈 <b>Trades en Sesión:</b> <code>{_state.get('total_trades_session', 0)}</code>"
            )
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /estado: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

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
                self.send_reply(chat_id, f"📭 No hay operaciones hoy (<code>{hoy}</code>).")
                return

            response = f"📊 <b>Historial de hoy ({hoy}):</b>\n\n"
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
                emoji = "🟢 LONG" if "LONG" in tipo or "buy" in tipo.lower() else "🔴 SHORT"
                hora = fecha.split()[1] if " " in fecha else fecha
                response += f"🔹 <b>{ticker}</b> | {emoji} <code>{hora}</code> — {pnl_str}\n"
            if pnl_count > 0:
                response += f"\n🏁 <b>PnL Cerrado Hoy:</b> <code>${total_pnl:+.2f}</code>"
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /historial_hoy: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_balance_posiciones(self, chat_id):
        try:
            if not self.broker_client or not self.broker_client.is_connected():
                self.send_reply(chat_id, "⚠️ Broker Alpaca no conectado.")
                return
            acc = self.broker_client.get_account_info()
            if not acc:
                self.send_reply(chat_id, "❌ No se pudo obtener info de cuenta.")
                return
            response = (
                f"💼 <b>Cartera Alpaca</b>\n"
                f"💳 Equity: <code>${acc.get('equity',0):,.2f}</code>\n"
                f"💵 Buying Power: <code>${acc.get('buying_power',0):,.2f}</code>\n\n"
            )
            positions = self.broker_client.get_open_positions()
            if not positions:
                response += "📭 Sin posiciones abiertas."
            else:
                response += "📌 <b>Posiciones:</b>\n"
                for p in positions:
                    side = "🟢 LONG" if p['side'] == 'long' else "🔴 SHORT"
                    response += f"{side} <b>{p['symbol']}</b>: {p['qty']} @ <code>${p['current_price']:,.2f}</code> | PnL: <b>${p['unrealized_pl']:+,.2f}</b>\n"
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /balance: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    # ═══════════════════════════════════════════════════════════════
    # Comandos de Capital y Alertas (Nivel 2)
    # ═══════════════════════════════════════════════════════════════

    def _cmd_monto(self, chat_id, args):
        try:
            if not args:
                config = get_config()
                current = config.get("trade_amount", 100)
                self.send_reply(chat_id, f"💵 Monto actual: <b>${current:,.2f}</b> USD.\nUsa <code>/monto 200</code> para cambiarlo.")
                return
            try:
                nuevo = float(args[0])
            except ValueError:
                self.send_reply(chat_id, "⚠️ Debe ser un número. Ej: <code>/monto 200</code>")
                return
            if nuevo < 10:
                self.send_reply(chat_id, "⚠️ Mínimo $10 USD.")
                return
            config = get_config()
            old = config.get("trade_amount", 100)
            config["trade_amount"] = nuevo
            save_config(config)
            self.send_reply(chat_id, f"✅ Monto: <b>${old:,.2f}</b> → <b>${nuevo:,.2f}</b> USD")
        except Exception as e:
            logging.error(f"Error en /monto: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_pnl(self, chat_id):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ticker, SUM(pnl), COUNT(*) FROM trades WHERE pnl IS NOT NULL AND fecha >= date('now','-7 days') GROUP BY ticker ORDER BY 2 DESC LIMIT 15"
            )
            rows = cursor.fetchall()
            if not rows:
                self.send_reply(chat_id, "📭 No hay trades cerrados en 7 días.")
                return
            response = "💰 <b>PnL 7 Días</b>\n\n"
            total = 0.0
            for t, pnl, cnt in rows:
                emoji = "📈" if pnl >= 0 else "📉"
                response += f"{emoji} <b>{t}</b>: <code>${pnl:+,.2f}</code> ({cnt} trades)\n"
                total += pnl
            response += f"\n{'🟢' if total>=0 else '🔴'} <b>Total:</b> <code>${total:+,.2f}</code>"
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /pnl: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_alerta(self, chat_id, args, direction):
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
                self.send_reply(chat_id, "⚠️ Precio positivo.")
                return
            aid = save_price_alert(ticker, target, direction)
            if aid > 0:
                txt = "supere" if direction == "ABOVE" else "caiga debajo de"
                self.send_reply(chat_id, f"✅ <b>Alerta #{aid}:</b> {ticker} cuando {txt} <code>${target:,.2f}</code>")
            else:
                self.send_reply(chat_id, "❌ No se pudo crear.")
        except Exception as e:
            logging.error(f"Error en /alerta: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_alertas(self, chat_id):
        try:
            alerts = get_price_alerts(active_only=True)
            if not alerts:
                self.send_reply(chat_id, "📭 Sin alertas.\nUsa <code>/alerta AAPL 200</code>")
                return
            response = "⏰ <b>Alertas Activas</b>\n\n"
            for a in alerts:
                d = "supere" if a['direction'] == 'ABOVE' else "caiga debajo de"
                response += f"🔔 <b>#{a['id']}</b> — {a['ticker']} cuando {d} <code>${a['target_price']:,.2f}</code>\n"
            self.send_reply(chat_id, response)
        except Exception as e:
            logging.error(f"Error en /alertas: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    def _cmd_borrar_alerta(self, chat_id, args):
        try:
            if not args:
                self.send_reply(chat_id, "⚠️ Uso: <code>/borrar_alerta 3</code>")
                return
            try:
                aid = int(args[0])
            except ValueError:
                self.send_reply(chat_id, "⚠️ ID numérico. Usa <code>/alertas</code>.")
                return
            if delete_price_alert(aid):
                self.send_reply(chat_id, f"🗑️ <b>Alerta #{aid} eliminada.</b>")
            else:
                self.send_reply(chat_id, f"⚠️ No se encontró #{aid}.")
        except Exception as e:
            logging.error(f"Error en /borrar_alerta: {e}")
            self.send_reply(chat_id, f"❌ Error: {str(e)}")

    # ═══════════════════════════════════════════════════════════════
    # Nivel 3 — Gráfico rápido
    # ═══════════════════════════════════════════════════════════════

    def _cmd_chart(self, chat_id, args):
        """Genera y envía un gráfico profesional de velas japonesas con EMAs + volumen."""
        try:
            ticker = args[0].upper().strip() if args else "SPY"
            self.send_reply(chat_id, f"📊 Generando gráfico para <b>{ticker}</b>...")

            from core.data_fetcher import get_stock_data
            from core.strategy import apply_strategy, get_spy_sentiment

            spy_sent = get_spy_sentiment()
            df = get_stock_data(ticker, period="5d", interval="15m")
            if df.empty or len(df) < 14:
                self.send_reply(chat_id, f"⚠️ Datos insuficientes para <b>{ticker}</b>.")
                return

            df_a = apply_strategy(df, spy_sentiment=spy_sent, ticker_symbol=ticker)
            plot_data = df_a.tail(60)  # 60 velas = ~15 horas de trading

            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
            import matplotlib.patches as mpatches
            from matplotlib.lines import Line2D
            from io import BytesIO
            import numpy as np

            # ── Configurar figura ──
            fig = plt.figure(figsize=(12, 8))
            fig.patch.set_facecolor('#131722')

            # Panel de velas (ocupa 65% superior)
            ax_candle = fig.add_axes([0.07, 0.30, 0.90, 0.65])
            ax_candle.set_facecolor('#131722')
            ax_candle.yaxis.tick_right()
            ax_candle.yaxis.set_label_position("right")

            # Panel de volumen (ocupa 15% inferior)
            ax_vol = fig.add_axes([0.07, 0.12, 0.90, 0.15], sharex=ax_candle)
            ax_vol.set_facecolor('#131722')
            ax_vol.yaxis.tick_right()
            ax_vol.yaxis.set_label_position("right")

            # ── Dibujar velas japonesas reales ──
            body_width = 0.0004  # Ancho del cuerpo
            for i in range(len(plot_data)):
                dt = mdates.date2num(plot_data.index[i])
                o, h, l, c = plot_data['Open'].iloc[i], plot_data['High'].iloc[i], plot_data['Low'].iloc[i], plot_data['Close'].iloc[i]
                bullish = c >= o
                color = '#26a69a' if bullish else '#ef5350'
                edge_color = '#1b7a6e' if bullish else '#c62828'

                # Mecha (sombra) — línea vertical fina
                ax_candle.plot([dt, dt], [l, h], color=edge_color, linewidth=1.0, solid_capstyle='round')

                # Cuerpo — rectángulo
                body_bottom = o if bullish else c
                body_height = abs(c - o)
                if body_height < 0.0001:
                    body_height = max(h - l, 0.01) * 0.01  # Doji: línea fina
                rect = mpatches.Rectangle(
                    (dt - body_width/2, body_bottom), body_width, body_height,
                    facecolor=color if body_height > 0.001 else edge_color,
                    edgecolor=edge_color, linewidth=0.5, zorder=3
                )
                ax_candle.add_patch(rect)

            # ── EMAs ──
            if 'EMA_20' in plot_data.columns:
                ax_candle.plot(plot_data.index, plot_data['EMA_20'], color='#FF9800', linewidth=1.2, label='EMA 20', zorder=4)
            if 'EMA_50' in plot_data.columns:
                ax_candle.plot(plot_data.index, plot_data['EMA_50'], color='#E91E63', linewidth=1.2, label='EMA 50', zorder=4)
            if 'EMA_200' in plot_data.columns:
                ax_candle.plot(plot_data.index, plot_data['EMA_200'], color='#42A5F5', linewidth=1.2, label='EMA 200', zorder=4)

            # ── Leyenda ──
            legend = ax_candle.legend(loc='upper left', fontsize=7, facecolor='#1e2233', edgecolor='#2a2e3e', labelcolor='#ccc', framealpha=0.9)
            legend.get_frame().set_linewidth(0.5)

            # ── Volumen ──
            vol_colors = ['#26a69a' if plot_data['Close'].iloc[i] >= plot_data['Open'].iloc[i] else '#ef5350' for i in range(len(plot_data))]
            ax_vol.bar(plot_data.index, plot_data['Volume'], color=vol_colors, width=0.0004, alpha=0.45, linewidth=0)
            ax_vol.set_ylabel('Volumen', color='#666', fontsize=7, labelpad=5)
            ax_vol.tick_params(colors='#555', labelsize=6)

            # ── Configurar ejes de velas ──
            ax_candle.tick_params(colors='#555', labelsize=7)
            ax_candle.grid(axis='y', alpha=0.08, color='white', linewidth=0.5)
            ax_candle.set_ylabel('Precio (USD)', color='#666', fontsize=7, labelpad=5)

            # ── Formatear eje X (fechas/horas) ──
            for ax in [ax_candle, ax_vol]:
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%a %d\n%H:%M'))
                ax.tick_params(axis='x', colors='#555', labelsize=6)
                ax.grid(axis='x', alpha=0.05, color='white', linewidth=0.5)

            # ── Línea de precio actual ──
            last_price = float(plot_data['Close'].iloc[-1])
            ax_candle.axhline(y=last_price, color='#FFD700', linewidth=0.8, linestyle='--', alpha=0.6, zorder=2)

            # ── Info Box en la parte superior ──
            score = int(plot_data['Score'].iloc[-1]) if 'Score' in plot_data.columns else 50
            ml_pred = df_a.attrs.get('ml_prediction', 50)
            scenario = plot_data['Market_Scenario'].iloc[-1] if 'Market_Scenario' in plot_data.columns else "Estándar"

            first_price = float(plot_data['Close'].iloc[0])
            change_pct = ((last_price - first_price) / first_price) * 100
            change_color = '#26a69a' if change_pct >= 0 else '#ef5350'
            change_sign = '+' if change_pct >= 0 else ''

            if score >= 65:
                signal_text = "🟢 COMPRA"
                signal_color = '#26a69a'
            elif score <= 35:
                signal_text = "🔴 VENTA"
                signal_color = '#ef5350'
            else:
                signal_text = "⚪ NEUTRAL"
                signal_color = '#888'

            info_text = (
                f"  {ticker}    │    ${last_price:,.2f}    │    {change_sign}{change_pct:.2f}%"
                f"    │    Score: {score}/100 {signal_text}"
            )
            fig.text(0.5, 0.965, info_text, transform=fig.transFigure,
                     fontsize=10, fontweight='bold', color='white',
                     fontfamily='monospace', ha='center', va='top',
                     bbox=dict(boxstyle='round,pad=0.4', facecolor='#1e2233',
                               edgecolor='#2a2e3e', linewidth=1, alpha=0.95))

            # ── Subtítulo con escenario y ML ──
            sub_text = f"Escenario: {scenario}    │    ML: {ml_pred}%    │    {plot_data.index[0].strftime('%m/%d')} → {plot_data.index[-1].strftime('%m/%d %H:%M')}"
            fig.text(0.5, 0.935, sub_text, transform=fig.transFigure,
                     fontsize=7, color='#888', fontfamily='monospace', ha='center', va='top')

            # ── Guardar en memoria ──
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=130, facecolor='#131722', bbox_inches='tight', pad_inches=0.3)
            buf.seek(0)
            plt.close(fig)

            # ── Enviar a Telegram ──
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            files = {'photo': (f'{ticker}_chart.png', buf, 'image/png')}
            data = {'chat_id': chat_id}
            resp = requests.post(url, data=data, files=files, timeout=15)
            if resp.status_code != 200:
                logging.error(f"Error enviando gráfico: {resp.text}")
                self.send_reply(chat_id, "❌ Error al enviar el gráfico.")
            buf.close()
        except Exception as e:
            logging.error(f"Error en /chart {args}: {e}")
            self.send_reply(chat_id, f"❌ Error generando gráfico: {str(e)}")

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