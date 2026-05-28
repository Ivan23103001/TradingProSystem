import time
import logging
import os
from datetime import datetime

from core.data_fetcher import get_stock_data
from core.strategy import apply_strategy
from core.broker import BrokerClient
from core.brain import TradingBrain
from core.notifier import TelegramNotifier
from core.simulator import is_market_open, check_critical_hours
from core.config import get_config, save_config, load_env
from core.database import init_db, save_trade, save_equity, update_last_trade_pnl
import pytz

# Memoria de estados para trazabilidad (Punto 5)
trade_reasons = {}
software_monitored = {}  # {symbol: {side, entry_price, sl_price, tp_price, time}}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    from core.health_server import start_health_server, _state
    from core.telegram_listener import TelegramListener
    logging.info("Iniciando Bot Worker 24/7...")
    start_health_server(port=8001)
    init_db()
    load_env()
    
    api_key = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")
    is_paper = str(os.getenv("ALPACA_PAPER", "True")).lower() == "true"
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    bc = BrokerClient(api_key, secret_key, paper=is_paper) if api_key and secret_key else None
    notifier = TelegramNotifier(bot_token, chat_id) if bot_token and chat_id else None

    # Iniciar escuchador interactivo de Telegram si hay credenciales
    if bot_token and chat_id:
        try:
            listener = TelegramListener(bot_token, chat_id, broker_client=bc)
            listener.start()
        except Exception as e:
            logging.error(f"No se pudo iniciar el escuchador de Telegram: {e}")

    if bc and bc.is_connected():
        logging.info("Broker Conectado Exitosamente.")
    else:
        logging.warning("Broker No Conectado. Revisa tus credenciales en el archivo .env")

    state_memory = {} # Para no repetir alertas/compras sobre la misma señal en el mismo día

    while True:
        try:
            config = get_config()
            auto_scan = config.get('auto_scan', False)
            auto_trade = config.get('auto_trade', False)
            
            if not auto_scan and not auto_trade:
                time.sleep(10) # Si no hay nada prendido, esperamos un poco
                continue
                
            mkt_open, mkt_msg = is_market_open()
            
            tickers_input = config.get('tickers', '')
            tickers = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
            
            stop_loss_pct = float(config.get('stop_loss_pct', 8.0))
            take_profit_pct = float(config.get('take_profit_pct', 15.0))
            interval = config.get('interval', '15m')
            period = config.get('period', '5d')

            # Direction Control Panel (IMP-6)
            direction_mode = config.get('direction_mode', TradingBrain.DIRECTION_MODE)
            long_amount = float(config.get('long_amount', TradingBrain.LONG_AMOUNT_USD))
            short_amount = float(config.get('short_amount', TradingBrain.SHORT_AMOUNT_USD))
            long_max_price = config.get('long_max_price', None)
            short_min_price = config.get('short_min_price', None)
            
            if not tickers:
                time.sleep(10)
                continue
                
            logging.info(f"Escaneando mercado... ({len(tickers)} tickers)")
            _state["last_scan"] = datetime.now().isoformat()
            
            # Fetch SPY sentiment once per cycle to optimize
            from core.strategy import get_spy_sentiment
            spy_sentiment = get_spy_sentiment()
            logging.info(f"Sentimiento del Mercado (SPY): {'BULL' if spy_sentiment == 1 else 'BEAR' if spy_sentiment == -1 else 'NEUTRAL'}")

            # =================================================================
            # IMP-5: WEEKLY AUTO-RETRAIN (Domingos)
            # =================================================================
            today_str = datetime.today().strftime('%Y-%m-%d')
            if datetime.today().weekday() == 6 and state_memory.get("last_retrain") != today_str:
                logging.info("📅 Domingo detectado — iniciando mantenimiento de DB y re-entrenamiento...")
                from core.database import archive_old_trades
                archive_old_trades(days_to_keep=90)
                try:
                    from core.ml_engine import train_trading_model
                    for ticker in tickers[:5]:
                        df_t = get_stock_data(ticker, period="2y", interval="1d")
                        if not df_t.empty and len(df_t) >= 100:
                            da_t = apply_strategy(df_t, ticker_symbol=ticker)
                            _, retrain_msg = train_trading_model(da_t, bars_forward=3, min_move_pct=0.015)
                            logging.info(f"🤖 Retrain {ticker}: {retrain_msg}")
                    state_memory["last_retrain"] = today_str
                    logging.info("✅ Re-entrenamiento semanal completado.")
                    if notifier:
                        notifier.send_message("✅ Modelo ML re-entrenado exitosamente (re-entrenamiento dominical).")
                except Exception as e:
                    logging.error(f"❌ Error en re-entrenamiento: {e}")

            # Filtro de Horarios Críticos (Punto 4)
            et = pytz.timezone('US/Eastern')
            now_est = datetime.now(et)
            safe_hour, hour_msg = check_critical_hours(now_est)
            
            # =================================================================
            # 0. TRACKING POSICIONES - Post-Mortem con Análisis Real de Alpaca
            # =================================================================
            if bc and bc.is_connected():
                current_positions = {p['symbol']: p for p in bc.get_open_positions()}
                old_positions = state_memory.get("active_positions", {})

                for t_old in old_positions:
                    if t_old not in current_positions:
                        # Posición cerrada - determinar MOTIVO REAL
                        reason = trade_reasons.get(t_old, None)

                        if not reason:
                            # Consultar historial de órdenes de Alpaca
                            reason = bc.determine_close_reason(t_old)

                        # Obtener precio de salida real para cálculo de PnL exacto
                        exit_price = 0.0
                        closed_ords = bc.get_closed_orders(symbol=t_old, limit=1)
                        if closed_ords:
                            exit_price = closed_ords[0].get('filled_avg_price', 0.0)
                        if exit_price == 0.0:
                            exit_price = state_memory.get(f"last_price_{t_old}", 0.0)
                            
                        # Guardar el PnL y motivo real en la base de datos centralizada
                        update_last_trade_pnl(t_old, exit_price, reason)

                        loss_count = state_memory.get("consecutive_losses", 0)

                        if reason in ('STOP_LOSS', 'SOFTWARE STOP LOSS'):
                            loss_count += 1
                            logging.warning(f"⚠️ PÉRDIDA (SL) en {t_old}. Consecutivas: {loss_count}/3")
                            if notifier:
                                notifier.send_message(f"⚠️ Stop Loss en {t_old}. Pérdidas consecutivas: {loss_count}/3")
                        elif reason in ('TAKE_PROFIT', 'SOFTWARE TAKE PROFIT', 'MANUAL'):
                            loss_count = 0
                            logging.info(f"✅ Cierre exitoso en {t_old} ({reason}). Reset pérdidas.")
                        else:
                            # UNKNOWN - no cambiar contador, ser neutral
                            logging.info(f"🔍 Cierre de {t_old} motivo: {reason}")

                        state_memory["consecutive_losses"] = loss_count

                        if loss_count >= 3:
                            cooldown_mins = 120
                            state_memory["circuit_breaker_until"] = time.time() + (cooldown_mins * 60)
                            msg_cb = f"🚨 CIRCUIT BREAKER: {loss_count} pérdidas seguidas. Pausa {cooldown_mins} min."
                            logging.error(msg_cb)
                            if notifier: notifier.send_message(msg_cb)

                        # Notificar cierre
                        msg = f"🔔 TRADE CERRADO: {t_old}\nMotivo: {reason}\nContexto: Posición liquidada en Alpaca."
                        logging.info(msg)
                        if notifier: notifier.send_message(msg)

                        # Guardar referencia para re-entrada inteligente
                        state_memory[f"last_sl_{t_old}"] = {
                            "price": state_memory.get(f"last_price_{t_old}", 0),
                            "time": time.time()
                        }
                        trade_reasons.pop(t_old, None)
                        software_monitored.pop(t_old, None)

                # Actualizar precios actuales para referencia
                for sym, pos in current_positions.items():
                    state_memory[f"last_price_{sym}"] = pos.get('current_price', 0)

                state_memory["active_positions"] = current_positions

            # =================================================================
            # IMP-2: MULTI-HORIZON CIRCUIT BREAKERS (DAILY/WEEKLY)
            # =================================================================
            today_date = datetime.today().strftime('%Y-%m-%d')
            current_week = datetime.today().isocalendar()[1]
            
            if state_memory.get("equity_week") != current_week:
                state_memory["equity_week"] = current_week
                state_memory["equity_week_start"] = None
                logging.info("📅 Nueva semana detectada. Reseteando tracking semanal.")
                
            if state_memory.get("equity_day_date") != today_date:
                state_memory["equity_day_date"] = today_date
                state_memory["equity_day_start"] = None
                state_memory["daily_loss_breaker"] = False
                cfg_reset = get_config()
                cfg_reset["daily_loss_breaker"] = False
                save_config(cfg_reset)
                logging.info("📅 Nuevo día detectado. Circuit Breaker diario reseteado.")

            if bc and bc.is_connected():
                acc_dl = bc.get_account_info()
                if acc_dl:
                    current_equity = acc_dl.get('equity', 0)
                    
                    if state_memory.get("equity_week_start") is None:
                        state_memory["equity_week_start"] = current_equity
                        logging.info(f"📊 Equity inicio de semana: ${current_equity:,.2f}")
                        
                    if state_memory.get("equity_day_start") is None:
                        state_memory["equity_day_start"] = current_equity
                        logging.info(f"📊 Equity inicio de día: ${current_equity:,.2f}")

                    breaker_active, level, msg_dl = TradingBrain.check_kill_switches(
                        current_equity,
                        state_memory.get("equity_day_start"),
                        state_memory.get("equity_week_start")
                    )
                    
                    if breaker_active and not state_memory.get("daily_loss_breaker", False):
                        state_memory["daily_loss_breaker"] = True
                        cfg_bl = get_config()
                        cfg_bl["daily_loss_breaker"] = True
                        save_config(cfg_bl)
                        logging.error(f"🚨 KILL SWITCH {level}: {msg_dl}")
                        if notifier:
                            notifier.send_message(f"🚨 KILL SWITCH {level}: {msg_dl}")

            # Conteo de posiciones abiertas (una vez por ciclo, para IMP-1)
            open_count = len(state_memory.get("active_positions", {}))

            # =================================================================
            # 1. MONITOREO SOFTWARE SL/TP - Protección para órdenes sin bracket
            # =================================================================
            if bc and bc.is_connected() and software_monitored:
                sw_positions = {p['symbol']: p for p in bc.get_open_positions()}
                symbols_to_remove = []

                for sym, monitor in software_monitored.items():
                    if sym not in sw_positions:
                        symbols_to_remove.append(sym)
                        continue

                    current_price = sw_positions[sym]['current_price']

                    triggered = False
                    trigger_type = ""

                    if monitor['side'] == 'buy':
                        if current_price <= monitor['sl_price']:
                            triggered, trigger_type = True, "STOP LOSS"
                        elif current_price >= monitor['tp_price']:
                            triggered, trigger_type = True, "TAKE PROFIT"
                    else:  # sell/short
                        if current_price >= monitor['sl_price']:
                            triggered, trigger_type = True, "STOP LOSS"
                        elif current_price <= monitor['tp_price']:
                            triggered, trigger_type = True, "TAKE PROFIT"

                    if triggered:
                        ok, close_msg = bc.close_position(sym)
                        if ok:
                            trade_reasons[sym] = f"SOFTWARE {trigger_type}"
                            emoji = "🛑" if "STOP" in trigger_type else "✅"
                            limit_price = monitor['sl_price'] if "STOP" in trigger_type else monitor['tp_price']
                            log_msg = (
                                f"{emoji} SOFTWARE {trigger_type}: {sym} @ ${current_price:.2f} "
                                f"(Límite: ${limit_price:.2f})"
                            )
                            if "STOP" in trigger_type:
                                logging.warning(log_msg)
                            else:
                                logging.info(log_msg)
                            if notifier:
                                notifier.send_message(log_msg)
                            symbols_to_remove.append(sym)

                for sym in symbols_to_remove:
                    software_monitored.pop(sym, None)

            # Check Circuit Breaker (flag, NO hace continue — permite scan y re-entradas)
            cb_until = state_memory.get("circuit_breaker_until", 0)
            circuit_breaker_active = time.time() < cb_until
            if circuit_breaker_active:
                mins_left = int((cb_until - time.time()) / 60)
                logging.info(f"⏸️ Circuit Breaker activo ({mins_left} min restantes) — Solo scan y re-entradas permitidas")

            # Leer configuración de gestión de riesgo
            use_atr_sl = config.get('use_atr_sl', True)

            for t in tickers:
                try:
                    df = get_stock_data(t, period=period, interval=interval)
                    if df.empty or len(df) < 50:
                        continue
                        
                    da = apply_strategy(df, spy_sentiment=spy_sentiment, ticker_symbol=t)
                    price = float(da['Close'].iloc[-1])
                    score = int(da['Score'].iloc[-1])
                    raw_signal = float(da['Signal'].iloc[-1])
                    ml_conf = int(da.attrs.get('ml_prediction', 50))
                    
                    if raw_signal >= 1.0:
                        signal = "LONG"
                    elif raw_signal <= -1.0:
                        signal = "SHORT"
                    else:
                        signal = "NEUTRAL"
                        
                    # Filtro Institucional "IA Gatekeeper": Ignorar señales buenas si la IA no aprueba
                    if signal == "LONG" and ml_conf < 55:
                        logging.debug(f"⚠️ Lock IA: Omitiendo LONG en {t} (ML {ml_conf}% < 55%)")
                        signal = "NEUTRAL"
                    elif signal == "SHORT" and ml_conf > 45:
                        logging.debug(f"⚠️ Lock IA: Omitiendo SHORT en {t} (ML {ml_conf}% > 45%)")
                        signal = "NEUTRAL"
                        
                    today_str = datetime.today().strftime('%Y-%m-%d')
                    mem_key = f"{t}_{today_str}"
                    
                    # Notificar si hay nueva señal y el scanner esta activo
                    if signal in ["LONG", "SHORT"] and auto_scan:
                        if state_memory.get(mem_key) != signal:
                            if notifier:
                                emoji = "🚀" if signal == "LONG" else "📉"
                                verb = "Comprar" if signal == "LONG" else "Vender"
                                msg = f"{emoji} SEÑAL {signal}: {t}\nPrecio: ${price:,.2f}\nScore: {score}/100\nAcción sugerida: {verb}"
                                notifier.send_message(msg)
                            state_memory[mem_key] = signal
                    
                    # Lógica de Trade
                    if auto_trade and mkt_open and signal in ["LONG", "SHORT"] and bc and bc.is_connected():

                        # IMP-1: Límite de posiciones concurrentes
                        if open_count >= TradingBrain.MAX_CONCURRENT_POSITIONS:
                            logging.info(f"⛔ Máx. {TradingBrain.MAX_CONCURRENT_POSITIONS} posiciones alcanzado. Omitiendo {t}")
                            continue

                        # IMP-2: Daily Loss Circuit Breaker
                        if state_memory.get("daily_loss_breaker", False):
                            logging.warning(f"🚨 Daily Loss Breaker activo. Bloqueando nueva entrada en {t}")
                            continue

                        # Direction Control Panel
                        if signal == "LONG" and direction_mode == "SHORT_ONLY":
                            continue
                        if signal == "SHORT" and direction_mode == "LONG_ONLY":
                            continue
                        if signal == "LONG" and long_max_price and price > float(long_max_price):
                            logging.debug(f"⛔ {t} LONG omitido: precio ${price:.2f} > máx ${long_max_price}")
                            continue
                        if signal == "SHORT" and short_min_price and price < float(short_min_price):
                            logging.debug(f"⛔ {t} SHORT omitido: precio ${price:.2f} < mín ${short_min_price}")
                            continue

                        can_trade = True
                        # Si no es horario seguro, bloquear nuevas entradas
                        if not safe_hour:
                            can_trade = False
                            logging.warning(f"Omitiendo entrada en {t} por horario crítico: {hour_msg}")

                        # Si Circuit Breaker activo, bloquear nuevas entradas normales
                        if circuit_breaker_active:
                            can_trade = False

                        # RE-ENTRADA INTELIGENTE: Recuperación de Shakeout
                        # (puede forzar entrada incluso durante Circuit Breaker o horario crítico)
                        is_reentry = False
                        last_sl_data = state_memory.get(f"last_sl_{t}")  # {price: X, time: Y}
                        if last_sl_data and signal == "LONG":
                            sl_age_mins = (time.time() - last_sl_data.get('time', 0)) / 60
                            if price > last_sl_data['price'] * 1.005 and sl_age_mins < 120:
                                is_reentry = True
                                can_trade = True  # Forzar entrada: Shakeout Recovery
                                logging.info(f"🚀 RE-ENTRADA SHAKEOUT: {t} (precio ${price:.2f} > SL ${last_sl_data['price']:.2f} +0.5%, hace {sl_age_mins:.0f} min)")

                        if can_trade and state_memory.get(f"last_trade_{t}") != signal:
                            # Monto base por dirección + cap de capital efficiency
                            base_amount = long_amount if signal == "LONG" else short_amount
                            try:
                                available_bp = bc.get_account_info().get('buying_power', 0)
                            except Exception:
                                available_bp = 0
                                
                            current_atr = float(da['ATR'].iloc[-1]) if 'ATR' in da.columns else 0.0
                            
                            # Volatility Target Sizing (ajusta monto según ATR)
                            sized_amount = TradingBrain.calculate_volatility_adjusted_size(base_amount, price, current_atr)
                                
                            final_trade_amount = max(
                                TradingBrain.MINIMUM_TRADE_USD,
                                min(sized_amount, available_bp * TradingBrain.MAX_POSITION_EQUITY_PCT)
                            )
                            logging.debug(f"{t} Monto {signal}: base=${base_amount:.2f} ATR Sized=${sized_amount:.2f} BP=${available_bp:,.0f} → final=${final_trade_amount:.2f}")

                            # Gestión de Riesgo Híbrida (ATR + Manual)
                            # Calcula valores manuales del dashboard como piso/techo
                            if signal == "LONG":
                                manual_sl = price * (1 - stop_loss_pct / 100.0)
                                manual_tp = price * (1 + take_profit_pct / 100.0)
                            else:
                                manual_sl = price * (1 + stop_loss_pct / 100.0)
                                manual_tp = price * (1 - take_profit_pct / 100.0)

                            if use_atr_sl and 'ATR' in da.columns:
                                atr_val = float(da['ATR'].iloc[-1])
                                # ATR dinámico: SL = 2.1 ATRs, TP = 4.2 ATRs (Ratio 2:1)
                                if signal == "LONG":
                                    atr_sl = price - (atr_val * 2.1)
                                    atr_tp = price + (atr_val * 4.2)
                                    # Híbrido: usar ATR pero acotado por manual
                                    # SL no puede ser MÁS agresivo que el manual (más cerca del precio)
                                    sl_price = min(atr_sl, manual_sl)
                                    # TP no puede ser MENOS ambicioso que el manual
                                    tp_price = max(atr_tp, manual_tp)
                                else:
                                    atr_sl = price + (atr_val * 2.1)
                                    atr_tp = price - (atr_val * 4.2)
                                    sl_price = max(atr_sl, manual_sl)
                                    tp_price = min(atr_tp, manual_tp)
                                logging.debug(f"{t} SL/TP Híbrido: ATR_SL=${atr_sl:.2f} Manual_SL=${manual_sl:.2f} → Final_SL=${sl_price:.2f}")
                            else:
                                # Modo manual puro: usar los valores del dashboard directamente
                                sl_price = manual_sl
                                tp_price = manual_tp

                            side = 'buy' if signal == "LONG" else 'sell'

                            # Siempre notional= para soporte de acciones fraccionarias
                            ok, msg, has_bracket = bc.execute_trade(
                                t, side,
                                take_profit_price=tp_price,
                                stop_loss_price=sl_price,
                                notional=final_trade_amount
                            )

                            if ok:
                                trade_type = f"AUTO-{signal} (Bracket)" if has_bracket else f"AUTO-{signal} (Software SL/TP)"
                                logging.info(f"TRADE EJECUTADO {t} {signal} - {msg}")
                                save_trade(t, trade_type, price, final_trade_amount, score)
                                state_memory[f"last_trade_{t}"] = signal

                                trade_reasons[t] = f"Señal cambiada a {signal} con Score {score}"

                                # Si no tiene bracket del broker, registrar para monitoreo software
                                if not has_bracket:
                                    software_monitored[t] = {
                                        'side': side,
                                        'entry_price': price,
                                        'sl_price': sl_price,
                                        'tp_price': tp_price,
                                        'time': time.time()
                                    }
                                    logging.info(f"📡 {t} → MONITOREO SOFTWARE (SL: ${sl_price:.2f} / TP: ${tp_price:.2f})")

                                # Limpiar memoria de SL si entramos de nuevo
                                if f"last_sl_{t}" in state_memory:
                                    del state_memory[f"last_sl_{t}"]
                            else:
                                logging.error(f"Error operando {t}: {msg}")
                                
                except Exception as e:
                    logging.error(f"Error procesando {t}: {e}")
            
            # Log equity for chart
            if bc and bc.is_connected():
                acc = bc.get_account_info()
                if acc:
                    save_equity(acc['equity'])
            
            # El loop principal corre cada minuto si el scan o trade están on
            time.sleep(60)
            
        except Exception as e:
            logging.error(f"Error crítico en loop principal: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
