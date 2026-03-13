import streamlit as st
import pandas as pd
import time
import os
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- CORE ---
from core.data_fetcher import get_stock_data
from core.strategy import apply_strategy
from core.simulator import run_simulation
from core.notifier import TelegramNotifier
from core.broker import BrokerClient
from ui.styles import apply_styles

# =============================================================================
# DATABASE
# =============================================================================
DB_NAME = "trade_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  fecha TEXT, ticker TEXT, tipo TEXT,
                  precio REAL, cantidad INTEGER, score INTEGER)''')
    conn.commit()
    conn.close()

def save_trade(ticker, tipo, precio, cantidad, score):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO trades (fecha, ticker, tipo, precio, cantidad, score) VALUES (?,?,?,?,?,?)",
              (fecha, ticker, tipo, precio, cantidad, score))
    conn.commit()
    conn.close()

def get_trade_history():
    if not os.path.exists(DB_NAME):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM trades ORDER BY id DESC", conn)
    conn.close()
    return df

init_db()

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(page_title="Trading Dashboard", page_icon="📈", layout="wide")
apply_styles()

# =============================================================================
# SESSION STATE
# =============================================================================
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = "AAPL.MX"

# =============================================================================
# SIDEBAR — All configuration goes here (clean, out of the way)
# =============================================================================
with st.sidebar:
    st.markdown("## 📊 Trading Dashboard")
    st.caption("Motor de Inserción Matemática con IA en Tiempo Real.")
    st.markdown("---")

    st.markdown("#### ⚙️ Configuration Panel")

    tickers_input = st.text_area(
        "Tickers (separados por comas):",
        value="AAPL.MX, TSLA.MX, AMZN.MX, MSFT.MX, GOOGL.MX",
        height=60
    )

    c1, c2 = st.columns(2)
    with c1:
        interval = st.selectbox("Intervalo:", ["1m", "5m", "15m", "1h", "1d"], index=2)
    with c2:
        period = st.selectbox("Periodo:", ["1d", "5d", "1mo", "6mo", "1y"], index=1)

    with st.expander("🔑 Credenciales Alpaca"):
        api_key = st.text_input("API Key:", value="", placeholder="Tu API Key...")
        secret_key = st.text_input("Secreto:", value="", type="password", placeholder="Tu Secret Key...")
        is_paper = st.checkbox("Modo Paper Trading", value=True)

    with st.expander("🔔 Telegram"):
        bot_token = st.text_input("Bot Token:", type="password")
        chat_id = st.text_input("Chat ID:", type="password")

    st.markdown("---")
    auto_scan = st.toggle("⚡ Modo Tiempo Real (60s)", value=False)
    auto_trade = st.toggle("🤖 Permitir Auto-Trading", value=False)

    trade_amount = st.number_input(
        "💵 Monto por operación (USD):",
        min_value=1.0, max_value=1000.0, value=5.0, step=1.0,
        help="Cuántos dólares arriesgar en cada compra/venta automática. Usa acciones fraccionarias."
    )

    st.markdown("")
    btn_run = st.button("✦ EJECUTAR ESCÁNER", use_container_width=True)

    # --- Broker Check ---
    st.markdown("---")
    broker_status = "Desconectado"
    account_info = None

    if api_key and secret_key and len(api_key) > 10:
        if 'broker_checked' not in st.session_state:
            try:
                bc = BrokerClient(api_key, secret_key, paper=is_paper)
                if bc.is_connected():
                    st.session_state['broker_checked'] = True
                    st.session_state['broker_info'] = bc.get_account_info()
                else:
                    st.session_state['broker_checked'] = False
            except Exception:
                st.session_state['broker_checked'] = False

        if st.session_state.get('broker_checked'):
            broker_status = "Conectado"
            account_info = st.session_state.get('broker_info')
            equity = float(account_info['equity']) if account_info else 0
            st.success(f"🟢 Conectado — ${equity:,.2f} USD")
        else:
            st.error("🔴 Desconectado")
    else:
        st.warning("Ingresa tus keys de Alpaca para conectar.")

# =============================================================================
# PARSE TICKERS
# =============================================================================
tickers_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip()]
if st.session_state.selected_ticker not in tickers_list and tickers_list:
    st.session_state.selected_ticker = tickers_list[0]

# =============================================================================
# MAIN CONTENT AREA
# =============================================================================

# --- ROW 1: Ticker selector buttons (horizontal) ---
ticker_cols = st.columns(len(tickers_list))
for i, t in enumerate(tickers_list):
    with ticker_cols[i]:
        btn_type = "primary" if t == st.session_state.selected_ticker else "secondary"
        if st.button(t, key=f"sel_{t}", use_container_width=True, type=btn_type):
            st.session_state.selected_ticker = t
            st.rerun()

# --- ROW 2: Price cards ---
st.markdown("#### 📈 Market Overview")
price_cols = st.columns(len(tickers_list))
for i, t in enumerate(tickers_list):
    with price_cols[i]:
        try:
            df_p = get_stock_data(t, period=period, interval=interval)
            if not df_p.empty and len(df_p) >= 2:
                price = df_p['Close'].iloc[-1]
                prev = df_p['Close'].iloc[-2]
                chg = ((price - prev) / prev) * 100
                st.metric(label=t, value=f"${price:,.2f}", delta=f"{chg:+.2f}%")
            else:
                st.metric(label=t, value="—", delta="Sin datos")
        except Exception:
            st.metric(label=t, value="—", delta=None)

# --- ROW 3: Main chart ---
selected = st.session_state.selected_ticker
st.markdown(f"##### 📊 {selected} — Deep Analysis")

df = get_stock_data(selected, period=period, interval=interval)
if not df.empty:
    df_a = apply_strategy(df)

    has_vol = 'Volume' in df_a.columns and df_a['Volume'].sum() > 0
    has_rsi = 'RSI' in df_a.columns

    n_rows = 1 + int(has_vol) + int(has_rsi)
    heights = [0.6] + ([0.2] if has_vol else []) + ([0.2] if has_rsi else [])

    fig = make_subplots(rows=n_rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=heights)

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df_a.index, open=df_a['Open'], high=df_a['High'],
        low=df_a['Low'], close=df_a['Close'], name='Precio',
        increasing_line_color='#00ff88', decreasing_line_color='#ff4b4b',
        increasing_fillcolor='#00ff88', decreasing_fillcolor='#ff4b4b'
    ), row=1, col=1)

    # EMAs
    fig.add_trace(go.Scatter(x=df_a.index, y=df_a['EMA_20'],
        line=dict(color='#ffa500', width=1.5), name='EMA 20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_a.index, y=df_a['EMA_50'],
        line=dict(color='#00d1ff', width=1.5), name='EMA 50'), row=1, col=1)

    # Bollinger
    if 'BB_High' in df_a.columns:
        fig.add_trace(go.Scatter(x=df_a.index, y=df_a['BB_High'],
            line=dict(color='rgba(168,85,247,0.3)', width=1, dash='dot'),
            showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df_a.index, y=df_a['BB_Low'],
            line=dict(color='rgba(168,85,247,0.3)', width=1, dash='dot'),
            fill='tonexty', fillcolor='rgba(168,85,247,0.04)',
            showlegend=False), row=1, col=1)

    r = 2
    # Volume
    if has_vol:
        vol_colors = ['#00ff88' if c >= o else '#ff4b4b'
                      for c, o in zip(df_a['Close'], df_a['Open'])]
        fig.add_trace(go.Bar(x=df_a.index, y=df_a['Volume'],
            marker_color=vol_colors, opacity=0.5, showlegend=False), row=r, col=1)
        r += 1

    # RSI
    if has_rsi:
        fig.add_trace(go.Scatter(x=df_a.index, y=df_a['RSI'],
            line=dict(color='#a855f7', width=2), name='RSI'), row=r, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,75,75,0.4)", row=r, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,255,136,0.4)", row=r, col=1)

    fig.update_layout(
        template='plotly_dark', height=460,
        margin=dict(l=0, r=0, t=10, b=20),
        xaxis_rangeslider_visible=False,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter', size=10, color='#8b949e'),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                    font=dict(size=9), bgcolor='rgba(0,0,0,0)'),
        yaxis=dict(showgrid=True, gridcolor='rgba(33,38,45,0.5)', side='right'),
    )
    if n_rows >= 2:
        fig.update_layout(yaxis2=dict(showgrid=False, side='right'))
    if n_rows >= 3:
        fig.update_layout(yaxis3=dict(showgrid=True, gridcolor='rgba(33,38,45,0.3)',
                                       side='right', range=[0, 100]))

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
else:
    st.warning(f"No hay datos disponibles para {selected}.")

# --- Status bar ---
s1 = "Activo" if auto_scan else "Manual"
s2 = "Habilitado" if auto_trade else "Deshabilitado"
dot = "🟢" if broker_status == "Conectado" else "🔴"
st.caption(f"📡 Escaneo: {s1}  •  {dot} Broker: Alpaca ({broker_status})  •  🤖 Auto-Trading: {s2}  •  💵 ${trade_amount:.0f} USD por operación")

# =============================================================================
# SCANNER RESULTS
# =============================================================================
if btn_run or auto_scan:
    st.markdown("---")
    st.markdown("#### 🏁 Resultados del Radar")
    results = []
    bar = st.progress(0)
    for idx, t in enumerate(tickers_list):
        bar.progress((idx + 1) / len(tickers_list))
        d = get_stock_data(t, period=period, interval=interval)
        if not d.empty:
            da = apply_strategy(d)
            price = da['Close'].iloc[-1]
            score = da['Score'].iloc[-1]

            if score >= 80:
                sig = "<span class='pill pill-buy'>COMPRA FUERTE</span>"
                if bot_token and chat_id:
                    TelegramNotifier(bot_token, chat_id).send_message(
                        f"🚀 {t}\nPrecio: ${price:,.2f}\nScore: {score}")
            elif score <= 20:
                sig = "<span class='pill pill-sell'>VENTA</span>"
            else:
                sig = "<span class='pill pill-neutral'>NEUTRAL</span>"

            if auto_trade and broker_status == "Conectado":
                bc = BrokerClient(api_key, secret_key, paper=is_paper)
                if score >= 85:
                    ok, msg = bc.execute_trade(t, 'buy', notional=trade_amount)
                    if ok:
                        save_trade(t, "AUTO-BUY", price, trade_amount, score)
                        st.toast(f"✅ Compra ${trade_amount:.0f} de {t}", icon="📈")
                elif score <= 15:
                    ok, msg = bc.execute_trade(t, 'sell', notional=trade_amount)
                    if ok:
                        save_trade(t, "AUTO-SELL", price, trade_amount, score)
                        st.toast(f"🛑 Venta ${trade_amount:.0f} de {t}", icon="📉")

            results.append({"Ticker": t, "Precio": f"${price:,.2f}",
                            "Score": score, "Señal": sig})
    bar.empty()
    if results:
        st.write(pd.DataFrame(results).to_html(escape=False, index=False), unsafe_allow_html=True)

if auto_scan:
    time.sleep(60)
    st.rerun()

# =============================================================================
# BOTTOM TABS
# =============================================================================
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📊 Analítica Pro", "🤖 Ejecución", "📜 Mi Historial"])

with tab1:
    a1, a2 = st.columns([1, 3])
    with a1:
        ticker_sim = st.text_input("Ticker:", value="AAPL")
        periodo_sim = st.selectbox("Historial:", ["1mo", "3mo", "6mo", "1y", "5y"], index=3)
        capital = st.number_input("Capital ($USD):", value=50000)
        btn_sim = st.button("🧪 INICIAR LABORATORIO", use_container_width=True)
    with a2:
        if btn_sim:
            df_lab = get_stock_data(ticker_sim, period=periodo_sim)
            if not df_lab.empty:
                df_r = apply_strategy(df_lab)
                met = run_simulation(df_r, initial_capital=capital)['metrics']
                m1, m2, m3 = st.columns(3)
                m1.metric("Retorno Neto", f"{met['net_return']:.2f}%")
                m2.metric("Win Rate", f"{met['win_rate']:.1f}%")
                m3.metric("Sharpe Ratio", f"{met['sharpe_ratio']:.2f}")

with tab2:
    if broker_status == "Conectado" and account_info:
        st.success(f"✅ Conectado — Equity: ${float(account_info['equity']):,.2f} USD")
        bc1, bc2 = st.columns(2)
        bc1.metric("Poder de Compra", f"${float(account_info['buying_power']):,.2f}")
        bc2.metric("Equity", f"${float(account_info['equity']):,.2f}")
    else:
        st.warning("⚠️ Ingresa tus credenciales en la barra lateral (🔑 Credenciales Alpaca).")

with tab3:
    df_h = get_trade_history()
    if not df_h.empty:
        st.dataframe(df_h, use_container_width=True)
    else:
        st.info("📭 Historial vacío.")
