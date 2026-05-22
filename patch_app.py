import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add get_config, save_config, load_env to session state initialization
sidebar_start = """# =============================================================================
# SIDEBAR — COMMAND CENTER
# =============================================================================
config = get_config()

with st.sidebar:"""

content = re.sub(r'# =============================================================================\s*# SIDEBAR — COMMAND CENTER\s*# =============================================================================\s*with st.sidebar:', sidebar_start, content)

# 1. Update tickers_input value
content = re.sub(r'value="AAPL, TSLA, AMZN, MSFT, GOOGL, NVDA, META, NFLX, AMD, INTC, JPM, V, WMT, DIS, JNJ, BRK-B, PG, UNH, HD, VZ",', r'value=config.get("tickers", "AAPL, TSLA, AMZN, MSFT"),', content)

# 2. Update controls
content = re.sub(r'auto_scan = st.toggle\("Scanner", value=False', r'auto_scan = st.toggle("Scanner", value=config.get("auto_scan", False)', content)
content = re.sub(r'auto_trade = st.toggle\("Auto-Bot", value=False', r'auto_trade = st.toggle("Auto-Bot", value=config.get("auto_trade", False)', content)
content = re.sub(r'value=5\.0, step=1\.0', r'value=float(config.get("trade_amount", 5.0)), step=1.0', content)

# 3. Update Risk Management defaults
content = re.sub(r'stop_loss_pct = st.slider\(.*?value=8,', r'stop_loss_pct = st.slider("Stop Loss Base (%)", min_value=1, max_value=20, value=int(config.get("stop_loss_pct", 8)),', content)
content = re.sub(r'take_profit_pct = st.slider\(.*?value=15,', r'take_profit_pct = st.slider("Take Profit (%)", min_value=2, max_value=50, value=int(config.get("take_profit_pct", 15)),', content)
content = re.sub(r'use_trailing = st.toggle\(.*?value=True,', r'use_trailing = st.toggle("🎯 Trailing Stop", value=config.get("use_trailing", True),', content)
content = re.sub(r'use_atr_sl = st.toggle\(.*?value=True,', r'use_atr_sl = st.toggle("📊 SL Dinámico (ATR)", value=config.get("use_atr_sl", True),', content)
content = re.sub(r'confirm_bars = st.slider\(.*?value=2,', r'confirm_bars = st.slider("Confirmación (velas)", min_value=1, max_value=5, value=int(config.get("confirm_bars", 2)),', content)
content = re.sub(r'cooldown = st.slider\(.*?value=5,', r'cooldown = st.slider("Cooldown (días)", min_value=0, max_value=10, value=int(config.get("cooldown", 5)),', content)

# 4. Save Config Block
save_config_block = """    btn_run = st.button("◆  INICIAR RADAR", use_container_width=True)

    # Save state to configuration
    new_config = {
        "tickers": tickers_input,
        "auto_scan": auto_scan,
        "auto_trade": auto_trade,
        "trade_amount": float(trade_amount),
        "stop_loss_pct": float(stop_loss_pct),
        "take_profit_pct": float(take_profit_pct),
        "use_trailing": use_trailing,
        "use_atr_sl": use_atr_sl,
        "confirm_bars": confirm_bars,
        "cooldown": cooldown
    }
    if new_config != {k: config.get(k) for k in new_config.keys()}:
        save_config(new_config)
"""
content = re.sub(r'    btn_run = st.button\("◆  INICIAR RADAR", use_container_width=True\)', save_config_block, content)

# 5. Broker Access and keys from .env
broker_access_old = r'    with st.expander\("🔑 Acceso Broker"\):.*?chat_id = st.text_input\("Chat ID", type="password"\)'
broker_access_new = """    with st.expander("🔑 Acceso Broker"):
        st.write("Credenciales cargadas desde archivo .env")
        api_key = os.getenv("ALPACA_API_KEY", "")
        secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        is_paper = str(os.getenv("ALPACA_PAPER", "True")).lower() == "true"
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        st.caption(f"Broker Keys: {'✅ OK' if api_key and secret_key else '❌ Faltan'} | Paper: {is_paper}")
        st.caption(f"Telegram Bot: {'✅ OK' if bot_token and chat_id else '❌ Faltan'}")"""

content = re.sub(broker_access_old, broker_access_new, content, flags=re.DOTALL)

# 6. Remove auto_scan block and auto_trade execution from app.py
# The auto_trade logic execution inside app.py shouldn't run since bot_worker does it. 
# We'll remove the part that checks `if auto_trade and broker_status == "Conectado" and mkt_open:`
auto_trade_regex = r'            # Auto-Trade \(con verificación de horario de mercado\).*?st\.error\(f"Error {t}: {msg}"\)'
content = re.sub(auto_trade_regex, '', content, flags=re.DOTALL)

# Remove the sleep(60)
sleep_regex = r'if auto_scan:\n\s+time\.sleep\(60\)\n\s+st\.rerun\(\)\n'
content = re.sub(sleep_regex, '', content)


with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("App patched successfully!")
