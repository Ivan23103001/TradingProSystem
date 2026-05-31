import re
import os
import shutil
import sys
from datetime import datetime

APP_FILE = "app.py"

def _create_backup():
    """Copia app.py a un backup con timestamp. Retorna la ruta del backup."""
    if not os.path.exists(APP_FILE):
        print(f"ERROR: {APP_FILE} no existe. Abortando.")
        sys.exit(1)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"app_backup_{ts}.py"
    shutil.copy2(APP_FILE, backup_path)
    print(f"Backup atómico creado: {backup_path}")
    return backup_path

def _restore_backup(backup_path):
    """Restaura el backup en caso de fallo de parcheo."""
    shutil.copy2(backup_path, APP_FILE)
    print(f"ROLLBACK ejecutado: {backup_path} → {APP_FILE}")

def _safe_sub(pattern, replacement, content, flags=0, label=""):
    """Aplica re.sub con validación. Lanza ValueError si no hay coincidencia."""
    new_content = re.sub(pattern, replacement, content, flags=flags)
    if new_content == content:
        raise ValueError(f"Regex no coincidió: {label}")
    return new_content

def main():
    backup_path = _create_backup()

    with open(APP_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        # Add get_config, save_config, load_env to session state initialization
        sidebar_start = """# =============================================================================
# SIDEBAR — COMMAND CENTER
# =============================================================================
config = get_config()

with st.sidebar:"""
        content = _safe_sub(
            r'# =============================================================================\s*# SIDEBAR — COMMAND CENTER\s*# =============================================================================\s*with st.sidebar:',
            sidebar_start, content, label="sidebar_start"
        )

        # 1. Update tickers_input value
        content = _safe_sub(
            r'value="AAPL, TSLA, AMZN, MSFT, GOOGL, NVDA, META, NFLX, AMD, INTC, JPM, V, WMT, DIS, JNJ, BRK-B, PG, UNH, HD, VZ",',
            r'value=config.get("tickers", "AAPL, TSLA, AMZN, MSFT"),', content,
            label="tickers_input"
        )

        # 2. Update controls
        content = _safe_sub(
            r'auto_scan = st.toggle\("Scanner", value=False',
            r'auto_scan = st.toggle("Scanner", value=config.get("auto_scan", False)', content,
            label="auto_scan"
        )
        content = _safe_sub(
            r'auto_trade = st.toggle\("Auto-Bot", value=False',
            r'auto_trade = st.toggle("Auto-Bot", value=config.get("auto_trade", False)', content,
            label="auto_trade"
        )
        content = _safe_sub(
            r'value=5\.0, step=1\.0',
            r'value=float(config.get("trade_amount", 5.0)), step=1.0', content,
            label="trade_amount"
        )

        # 3. Update Risk Management defaults
        content = _safe_sub(
            r'stop_loss_pct = st.slider\(.*?value=8,',
            r'stop_loss_pct = st.slider("Stop Loss Base (%)", min_value=1, max_value=20, value=int(config.get("stop_loss_pct", 8)),', content,
            label="stop_loss_pct"
        )
        content = _safe_sub(
            r'take_profit_pct = st.slider\(.*?value=15,',
            r'take_profit_pct = st.slider("Take Profit (%)", min_value=2, max_value=50, value=int(config.get("take_profit_pct", 15)),', content,
            label="take_profit_pct"
        )
        content = _safe_sub(
            r'use_trailing = st.toggle\(.*?value=True,',
            r'use_trailing = st.toggle("🎯 Trailing Stop", value=config.get("use_trailing", True),', content,
            label="use_trailing"
        )
        content = _safe_sub(
            r'use_atr_sl = st.toggle\(.*?value=True,',
            r'use_atr_sl = st.toggle("📊 SL Dinámico (ATR)", value=config.get("use_atr_sl", True),', content,
            label="use_atr_sl"
        )
        content = _safe_sub(
            r'confirm_bars = st.slider\(.*?value=2,',
            r'confirm_bars = st.slider("Confirmación (velas)", min_value=1, max_value=5, value=int(config.get("confirm_bars", 2)),', content,
            label="confirm_bars"
        )
        content = _safe_sub(
            r'cooldown = st.slider\(.*?value=5,',
            r'cooldown = st.slider("Cooldown (días)", min_value=0, max_value=10, value=int(config.get("cooldown", 5)),', content,
            label="cooldown"
        )

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
        content = _safe_sub(
            r'    btn_run = st.button\("◆  INICIAR RADAR", use_container_width=True\)',
            save_config_block, content, label="save_config_block"
        )

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
        content = _safe_sub(
            broker_access_old, broker_access_new, content, flags=re.DOTALL,
            label="broker_access"
        )

        # 6. Remove auto_trade execution from app.py (non-critical — no rollback on fail)
        auto_trade_regex = r'            # Auto-Trade \(con verificación de horario de mercado\).*?st\.error\(f"Error {t}: {msg}"\)'
        content_after = re.sub(auto_trade_regex, '', content, flags=re.DOTALL)
        if content_after == content:
            print("⚠️  Aviso: Regex auto_trade no coincidió (posiblemente ya parcheado). Continuando...")
        content = content_after

        # 7. Remove the sleep(60) (non-critical)
        sleep_regex = r'if auto_scan:\n\s+time\.sleep\(60\)\n\s+st\.rerun\(\)\n'
        content_after = re.sub(sleep_regex, '', content)
        if content_after == content:
            print("⚠️  Aviso: Regex sleep/rerun no coincidió (posiblemente ya parcheado). Continuando...")
        content = content_after

        # Write patched content atomically: write to temp file, then rename
        tmp_path = APP_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, APP_FILE)

        print("App patched successfully!")
        # Limpiar backups viejos (mantener solo los 3 más recientes)
        backups = sorted(
            [f for f in os.listdir(".") if f.startswith("app_backup_") and f.endswith(".py")],
            key=lambda x: os.path.getmtime(x),
            reverse=True
        )
        for old in backups[3:]:
            os.remove(old)
            print(f"Backup antiguo eliminado: {old}")

    except Exception as e:
        print(f"ERROR durante el parcheo: {e}")
        print("Ejecutando ROLLBACK...")
        _restore_backup(backup_path)
        sys.exit(1)

if __name__ == "__main__":
    main()