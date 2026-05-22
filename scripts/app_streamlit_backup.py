import streamlit as st
import pandas as pd
import time
import os
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TradingProUI")

# --- CORE ---
from core.data_fetcher import get_stock_data
from core.strategy import apply_strategy, get_spy_sentiment
from core.simulator import run_simulation, is_market_open
from core.notifier import TelegramNotifier
from core.broker import BrokerClient
from ui.styles import apply_styles
from core.config import get_config, save_config, load_env
from core.database import init_db, save_trade, get_trade_history, get_equity_history
from core.ml_engine import calculate_ml_rolling_accuracy
from core.brain import TradingBrain

load_env()
init_db()

@st.cache_resource
def get_broker_client():
    """Crea el BrokerClient una sola vez y lo reutiliza entre renders."""
    api_key = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")
    paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
    if api_key and secret_key:
        return BrokerClient(api_key, secret_key, paper=paper)
    return None

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(page_title="Trading Pro System v5.0", page_icon="📊", layout="wide")
apply_styles()

# SESSION STATE
if 'selected_ticker' not in st.session_state:
    st.session_state.selected_ticker = "AAPL"

# =============================================================================
# SIDEBAR — CENTRO DE CONTROL
# =============================================================================
config = get_config()
with st.sidebar:
    st.markdown("# ⚡ PRO TERMINAL")
    st.markdown('<div class="help-text">Panel de control centralizado</div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- WATCHLIST ---
    st.markdown('<div class="section-title">📋 Watchlist</div>', unsafe_allow_html=True)
    tickers_input = st.text_area(
        "Tickers (separados por coma)",
        value=config.get("tickers", "AAPL, TSLA, MSFT, NVDA, AMZN, GOOGL, META, AMD, NFLX, JPM"),
        height=60, label_visibility="collapsed",
        help="Escribe los símbolos de las acciones que quieres monitorear, separados por coma."
    )
    import re
    def _valid_ticker(t):
        return bool(re.match(r'^[A-Z0-9\.\-]{1,10}$', t.strip().upper()))
    tickers_list = [t.strip().upper() for t in tickers_input.split(',') if t.strip() and _valid_ticker(t)]

    # --- TIMEFRAME ---
    st.markdown('<div class="section-title">⏱ Timeframe</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    intervals = ["1m", "5m", "15m", "1h", "1d"]
    periods = ["1d", "5d", "1mo", "6mo", "1y"]
    with c1:
        interval = st.selectbox(
            "Intervalo", intervals,
            index=intervals.index(config.get("interval", "15m")),
            help="Cada cuánto tiempo se forma una vela en el gráfico."
        )
    with c2:
        period = st.selectbox(
            "Período", periods,
            index=periods.index(config.get("period", "5d")),
            help="Cuánto historial vamos a analizar."
        )

    st.markdown("---")

    # --- AUTO MODES ---
    st.markdown('<div class="section-title">🤖 Automatización</div>', unsafe_allow_html=True)
    ct1, ct2 = st.columns(2)
    with ct1:
        auto_scan = st.toggle("Scanner", value=config.get("auto_scan", False),
                               help="Revisa continuamente todas las acciones buscando oportunidades.")
    with ct2:
        auto_trade = st.toggle("Auto-Bot", value=config.get("auto_trade", False),
                                help="⚠️ Ejecuta compras/ventas automáticamente cuando encuentra señales.")

    # --- SIZING ---
    st.markdown('<div class="section-title">💰 Tamaño de Posición</div>', unsafe_allow_html=True)
    trade_amount = st.number_input(
        "Monto por operación (USD)",
        value=float(config.get("trade_amount", 100.0)),
        min_value=1.0, step=10.0,
        help="Cuánto dinero invertir en cada operación automática."
    )

    # --- RISK ---
    with st.expander("🛡️ Control de Riesgo", expanded=False):
        st.markdown('<div class="help-text">Define cuánto estás dispuesto a perder y ganar por operación.</div>', unsafe_allow_html=True)
        sl_b = st.slider(
            "🔴 Stop Loss (%)", 1, 20,
            int(config.get("stop_loss_pct", 8)),
            help="Si el precio baja este porcentaje desde la compra, se vende automáticamente para limitar pérdidas."
        )
        tp_b = st.slider(
            "🟢 Take Profit (%)", 2, 50,
            int(config.get("take_profit_pct", 15)),
            help="Si el precio sube este porcentaje desde la compra, se vende automáticamente para asegurar ganancias."
        )
        use_atr = st.toggle(
            "ATR Dinámico",
            value=config.get("use_atr_sl", True),
            help="Ajusta automáticamente los niveles de SL/TP según la volatilidad del mercado (recomendado)."
        )
        k_frac = st.slider(
            "Fracción Kelly", 0.1, 1.0,
            float(config.get("kelly_fraction", 0.5)),
            step=0.1,
            help="Qué porcentaje del tamaño óptimo de Kelly usar. 0.5 = medio Kelly (más conservador)."
        )

    # --- DIRECTION CONTROL ---
    with st.expander("🎯 Modo de Operación", expanded=False):
        direction_mode = st.radio(
            "Dirección",
            ["LONG_ONLY", "SHORT_ONLY", "BOTH"],
            index=["LONG_ONLY", "SHORT_ONLY", "BOTH"].index(config.get("direction_mode", "BOTH")),
            help="LONG_ONLY: solo compras. SHORT_ONLY: solo ventas. BOTH: ambas direcciones."
        )
        c_l, c_s = st.columns(2)
        with c_l:
            long_amount = st.number_input(
                "📈 Monto LONG ($)", min_value=1.0,
                value=float(config.get("long_amount", TradingBrain.LONG_AMOUNT_USD)),
                step=10.0
            )
        with c_s:
            short_amount = st.number_input(
                "📉 Monto SHORT ($)", min_value=1.0,
                value=float(config.get("short_amount", TradingBrain.SHORT_AMOUNT_USD)),
                step=10.0
            )
        c_lp, c_sp = st.columns(2)
        with c_lp:
            long_max_price = st.number_input(
                "Precio máx. LONG ($)", min_value=0.0,
                value=float(config.get("long_max_price") or 0.0),
                step=5.0,
                help="No entrar en LONG si el precio supera este valor. 0 = sin límite."
            )
        with c_sp:
            short_min_price = st.number_input(
                "Precio mín. SHORT ($)", min_value=0.0,
                value=float(config.get("short_min_price") or 0.0),
                step=5.0,
                help="No entrar en SHORT si el precio está por debajo de este valor. 0 = sin límite."
            )

    # --- ACTIONS ---
    st.markdown("---")
    btn_run = st.button("◆  INICIAR ANÁLISIS", use_container_width=True, type="primary")

    # --- GUARDAR CONFIG ---
    new_config = {
        **config,
        "tickers": tickers_input,
        "interval": interval,
        "period": period,
        "auto_scan": auto_scan,
        "auto_trade": auto_trade,
        "trade_amount": float(config.get("trade_amount", 100.0)),
        "stop_loss_pct": sl_b,
        "take_profit_pct": tp_b,
        "use_atr_sl": use_atr,
        "kelly_fraction": k_frac,
        "direction_mode": direction_mode,
        "long_amount": long_amount,
        "short_amount": short_amount,
        "long_max_price": long_max_price if long_max_price > 0 else None,
        "short_min_price": short_min_price if short_min_price > 0 else None,
    }
    if new_config != config:
        save_config(new_config)

    # --- DAILY LOSS BREAKER WARNING ---
    if config.get("daily_loss_breaker", False):
        st.error("🚨 **CIRCUIT BREAKER DIARIO ACTIVO**\nPérdida ≥ 3%. Nuevas entradas bloqueadas hasta mañana.")

    # --- STATUS ---
    m_open, m_msg = is_market_open()
    dot_class = "status-dot-green pulse-active" if m_open else "status-dot-amber"
    st.markdown("---")
    st.markdown(f'''
    <div style="background:rgba(255,255,255,0.03);border-radius:8px;padding:10px 12px;">
        <div class="status-bar">
            <div class="status-item">
                <div class="status-dot {dot_class}"></div>{m_msg}
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)


# =============================================================================
# HEADER PRINCIPAL
# =============================================================================
now_str = datetime.now().strftime("%H:%M:%S")
st.markdown(f'''
<div class="header-bar">
    <div>
        <div class="header-title">
            📊 Trading Pro System
            <span class="header-version">v5.0 · Adaptive AI</span>
        </div>
        <div class="header-subtitle">SMC · Volume Imbalances · Ensamble RF+GB · Kill Switches · Kelly Dinámico</div>
    </div>
    <div class="header-badge">
        <div class="status-dot status-dot-green pulse-active"></div>
        LIVE · {now_str}
    </div>
</div>
''', unsafe_allow_html=True)


# =============================================================================
# HEATMAP DE TICKERS — Vista rápida de todas las acciones
# =============================================================================
st.markdown('<div class="section-title">🗺️ Mapa de Mercado</div>', unsafe_allow_html=True)
st.markdown('<div class="help-text">Haz clic en cualquier acción para ver su análisis detallado. Verde = señal de compra, Rojo = señal de venta, Gris = esperar.</div>', unsafe_allow_html=True)

spy_sentiment = get_spy_sentiment()
cols = st.columns(min(6, len(tickers_list)))
for idx, t in enumerate(tickers_list[:12]):
    with cols[idx % len(cols)]:
        try:
            df_t = get_stock_data(t, period=period, interval=interval)
            if df_t.empty or len(df_t) < 50:
                st.button(f"⚠️ {t}", key=f"e_{t}", use_container_width=True, disabled=True)
                continue
            df_t = apply_strategy(df_t, spy_sentiment=spy_sentiment, ticker_symbol=t)
            score = int(df_t['Score'].iloc[-1])
            price = df_t['Close'].iloc[-1]
            p_chg = ((price - df_t['Close'].iloc[-2]) / df_t['Close'].iloc[-2]) * 100 if len(df_t) > 1 else 0

            # Color del botón
            if score >= 65:
                emoji = "🟢"
            elif score <= 35:
                emoji = "🔴"
            else:
                emoji = "⚪"

            label = f"{emoji} **{t}**\n${price:,.2f} ({p_chg:+.1f}%)"
            if st.button(label, key=f"h_{t}", use_container_width=True):
                st.session_state.selected_ticker = t
                st.rerun()
        except Exception:
            st.button(f"⚠️ {t}", key=f"err_{t}", use_container_width=True, disabled=True)

st.markdown("---")

# =============================================================================
# ANÁLISIS PRINCIPAL DEL TICKER SELECCIONADO
# =============================================================================
selected = st.session_state.selected_ticker
df = get_stock_data(selected, period=period, interval=interval)

if not df.empty and len(df) >= 50:
    df_a = apply_strategy(df, spy_sentiment=spy_sentiment, ticker_symbol=selected)
    score = int(df_a['Score'].iloc[-1])
    price = float(df_a['Close'].iloc[-1])
    atr_val = float(df_a['ATR'].iloc[-1]) if 'ATR' in df_a.columns else 0
    ml_pred = df_a.attrs.get('ml_prediction', 50)
    k_val = df_a.attrs.get('kelly_size', 0.15) * k_frac
    scenario = df_a['Market_Scenario'].iloc[-1] if 'Market_Scenario' in df_a.columns else "Estándar"
    rsi_val = float(df_a['RSI'].iloc[-1]) if 'RSI' in df_a.columns else 50
    z_score = float(df_a['Z_Score'].iloc[-1]) if 'Z_Score' in df_a.columns else 0
    vol_imbalance_up = bool(df_a['Volume_Imbalance_Up'].iloc[-1]) if 'Volume_Imbalance_Up' in df_a.columns else False
    vol_imbalance_dn = bool(df_a['Volume_Imbalance_Down'].iloc[-1]) if 'Volume_Imbalance_Down' in df_a.columns else False

    # Fase 3: Estado adaptativo del modelo
    try:
        ml_rolling_acc, ml_dynamic_weight = calculate_ml_rolling_accuracy()
    except Exception:
        ml_rolling_acc, ml_dynamic_weight = 0.50, 0.40

    # Fase 1: Kill Switch state
    ks_daily = config.get("daily_loss_breaker", False)
    ks_weekly = config.get("weekly_loss_breaker", False)

    # Determinar señal para usuario
    raw_signal = float(df_a['Signal'].iloc[-1])
    if raw_signal >= 1.0:
        signal_text, signal_class, signal_emoji = "COMPRAR", "long", "🟢"
        signal_explain = "El sistema detecta una oportunidad de compra basada en múltiples indicadores."
    elif raw_signal <= -1.0:
        signal_text, signal_class, signal_emoji = "VENDER", "short", "🔴"
        signal_explain = "El sistema detecta señales de venta. El precio podría bajar."
    else:
        signal_text, signal_class, signal_emoji = "ESPERAR", "wait", "⏸️"
        signal_explain = "No hay señal clara. El sistema recomienda esperar una mejor oportunidad."

    # Score class
    if score >= 60:
        score_class = "bull"
    elif score <= 40:
        score_class = "bear"
    else:
        score_class = "neutral"

    # ----- ROW 1: Resumen rápido + Signal -----
    st.markdown(f'<div class="section-title">{signal_emoji} Análisis: {selected}</div>', unsafe_allow_html=True)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        delta_pct = ((price - df_a['Close'].iloc[-2]) / df_a['Close'].iloc[-2]) * 100 if len(df_a) > 1 else 0
        st.metric("💰 Precio Actual", f"${price:,.2f}", delta=f"{delta_pct:+.2f}%",
                  help="Último precio de la acción.")
    with m2:
        st.metric("📊 Score", f"{score}/100",
                  help="Puntuación de 0 a 100. Mayor a 70 = comprar, menor a 30 = vender.")
    with m3:
        st.metric("📈 RSI", f"{rsi_val:.0f}",
                  help="RSI: Mayor a 70 = sobrecomprado, menor a 30 = sobrevendido.")
    with m4:
        st.metric("📐 ATR (Sizing)", f"${atr_val:.2f}",
                  help="Fase 1: El tamaño de posición se ajusta dinámicamente por ATR para controlar el riesgo.")
    with m5:
        ks_label = "🚨 ACTIVO" if (ks_daily or ks_weekly) else "🟢 Normal"
        st.metric("🛑 Kill Switch", ks_label,
                  help="Fase 1: Circuit breaker automático — Diario ≥3% o Semanal ≥5% de pérdida.")


    # ----- Signal + Score visual -----
    sig_col, score_col = st.columns([1, 2])
    with sig_col:
        st.markdown(f'''
        <div class="glass-card">
            <div class="glass-card-title">Señal del Sistema</div>
            <div class="signal-badge {signal_class}">{signal_emoji} {signal_text}</div>
            <div class="help-text" style="margin-top:10px;">{signal_explain}</div>
        </div>
        ''', unsafe_allow_html=True)
    with score_col:
        st.markdown(f'''
        <div class="glass-card">
            <div class="glass-card-title">Nivel de Convicción</div>
            <div class="score-gauge">
                <div class="score-value {score_class}">{score}</div>
                <div style="flex:1;">
                    <div class="score-bar">
                        <div class="score-bar-fill {score_class}" style="width:{score}%;"></div>
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:4px;">
                        <span class="score-label">🔴 Vender</span>
                        <span class="score-label">⚪ Neutro</span>
                        <span class="score-label">🟢 Comprar</span>
                    </div>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    # ----- IA Adaptativa + Kelly + Volume Imbalance (Fases 2 y 3) -----
    ml_col, kelly_col, vol_col = st.columns(3)
    with ml_col:
        if ml_pred >= 65:
            ml_class, ml_label = "high", "OPTIMISTA"
        elif ml_pred <= 35:
            ml_class, ml_label = "low", "PESIMISTA"
        else:
            ml_class, ml_label = "mid", "NEUTRAL"
        # Estilo del peso adaptativo
        if ml_dynamic_weight >= 0.50:
            weight_color = "var(--accent-green)"
            weight_tag = "↑ Alto"
        elif ml_dynamic_weight >= 0.35:
            weight_color = "var(--accent-purple)"
            weight_tag = "Estándar"
        else:
            weight_color = "var(--accent-amber)"
            weight_tag = "↓ Bajo (Protección)"
        st.markdown(f'''
        <div class="ml-indicator">
            <span class="ml-icon">🤖</span>
            <div style="flex:1;">
                <div class="ml-label">Ensamble RF+GB &mdash; Fase 3 Adaptativa</div>
                <div class="ml-value {ml_class}">{ml_pred}% &mdash; {ml_label}</div>
                <div style="font-size:0.6rem;margin-top:4px;display:flex;gap:12px;">
                    <span>Win-Rate: <b style="color:var(--accent-cyan);">{ml_rolling_acc*100:.0f}%</b></span>
                    <span>Peso IA: <b style="color:{weight_color};">{ml_dynamic_weight*100:.0f}% {weight_tag}</b></span>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        st.markdown('<div class="help-text">Fase 3: Ensamble RF+GB con Robust Scaling. El peso se autoajusta según el Win-Rate real de los últimos 15 trades.</div>', unsafe_allow_html=True)

    with kelly_col:
        st.markdown(f'''
        <div class="ml-indicator" style="border-color:rgba(6,182,212,0.15);background:rgba(6,182,212,0.06);">
            <span class="ml-icon">📀</span>
            <div style="flex:1;">
                <div class="ml-label">Tamaño Óptimo (Kelly Dinámico)</div>
                <div class="ml-value mid" style="color:var(--accent-cyan);">{k_val*100:.1f}%</div>
                <div style="font-size:0.6rem;margin-top:4px;color:var(--text-dim);">del Capital Disponible</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        st.markdown('<div class="help-text">Fase 1+3: Kelly ajustado por volatilidad ATR y fracciado para máxima protección del capital.</div>', unsafe_allow_html=True)

    with vol_col:
        if vol_imbalance_up:
            vi_color = "rgba(16,185,129,0.12)"
            vi_border = "rgba(16,185,129,0.3)"
            vi_text = "🟢 COMPRADOR"
            vi_label_color = "var(--accent-green)"
        elif vol_imbalance_dn:
            vi_color = "rgba(239,68,68,0.12)"
            vi_border = "rgba(239,68,68,0.3)"
            vi_text = "🔴 VENDEDOR"
            vi_label_color = "var(--accent-red)"
        else:
            vi_color = "rgba(148,163,184,0.05)"
            vi_border = "rgba(148,163,184,0.15)"
            vi_text = "⚪ Sin Imbalance"
            vi_label_color = "var(--text-muted)"
        st.markdown(f'''
        <div class="ml-indicator" style="background:{vi_color};border-color:{vi_border};">
            <span class="ml-icon">🌊</span>
            <div style="flex:1;">
                <div class="ml-label">Imbalance de Volumen &mdash; Fase 2</div>
                <div class="ml-value" style="color:{vi_label_color};font-size:1rem;">{vi_text}</div>
                <div style="font-size:0.6rem;margin-top:4px;color:var(--text-dim);">Volumen &gt; 1.8x Media 20 velas</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        st.markdown(f'<div class="help-text">Fase 2: {scenario}</div>', unsafe_allow_html=True)

    # ----- GRÁFICO PRINCIPAL -----

    st.markdown('<div class="section-title">📈 Gráfico con Indicadores</div>', unsafe_allow_html=True)
    st.markdown('<div class="help-text">Velas verdes = el precio subió. Velas rojas = el precio bajó. Las líneas y triángulos son señales del sistema.</div>', unsafe_allow_html=True)

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=("", "Volumen", "RSI (Fuerza)")
    )
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df_a.index, open=df_a['Open'], high=df_a['High'], low=df_a['Low'], close=df_a['Close'],
        name='Precio', increasing_line_color='#10b981', decreasing_line_color='#ef4444',
        increasing_fillcolor='#10b981', decreasing_fillcolor='#ef4444'
    ), row=1, col=1)

    # EMAs
    fig.add_trace(go.Scatter(
        x=df_a.index, y=df_a['EMA_20'],
        line=dict(color='#f59e0b', width=1.5), name='Tendencia Corta (EMA 20)',
        opacity=0.8
    ), row=1, col=1)
    if 'EMA_50' in df_a.columns:
        fig.add_trace(go.Scatter(
            x=df_a.index, y=df_a['EMA_50'],
            line=dict(color='#8b5cf6', width=1.2, dash='dot'), name='Tendencia Media (EMA 50)',
            opacity=0.6
        ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_a.index, y=df_a['EMA_200'],
        line=dict(color='#3b82f6', width=1, dash='dash'), name='Tendencia Larga (EMA 200)',
        opacity=0.5
    ), row=1, col=1)

    # Order Blocks
    if 'Bullish_OB' in df_a.columns:
        last_20 = df_a['Bullish_OB'].iloc[-20:]
        bull_ob = last_20[last_20 > 0]
        if not bull_ob.empty:
            fig.add_hline(y=bull_ob.iloc[-1], line_dash="dash", line_color="rgba(16,185,129,0.5)",
                          row=1, col=1, annotation_text="🟢 Zona Compra (OB)")
    if 'Bearish_OB' in df_a.columns:
        last_20 = df_a['Bearish_OB'].iloc[-20:]
        bear_ob = last_20[last_20 > 0]
        if not bear_ob.empty:
            fig.add_hline(y=bear_ob.iloc[-1], line_dash="dash", line_color="rgba(239,68,68,0.5)",
                          row=1, col=1, annotation_text="🔴 Zona Venta (OB)")

    # Liquidity Sweeps
    if 'Bullish_Sweep_Signal' in df_a.columns:
        sw = df_a[df_a['Bullish_Sweep_Signal'] > 0]
        if not sw.empty:
            fig.add_trace(go.Scatter(
                x=sw.index, y=sw['Low'] * 0.999, mode='markers',
                marker=dict(symbol='triangle-up', size=12, color='#10b981', line=dict(width=1, color='#059669')),
                name='🧹 Barrido Alcista'
            ), row=1, col=1)
    if 'Bearish_Sweep_Signal' in df_a.columns:
        sw = df_a[df_a['Bearish_Sweep_Signal'] > 0]
        if not sw.empty:
            fig.add_trace(go.Scatter(
                x=sw.index, y=sw['High'] * 1.001, mode='markers',
                marker=dict(symbol='triangle-down', size=12, color='#ef4444', line=dict(width=1, color='#dc2626')),
                name='🧹 Barrido Bajista'
            ), row=1, col=1)

    # Volume — con destacado de Imbalances institucionales (Fase 2)
    if 'Volume_Imbalance_Up' in df_a.columns and 'Volume_Imbalance_Down' in df_a.columns:
        colors_vol = []
        for c, o, vi_up, vi_dn in zip(df_a['Close'], df_a['Open'],
                                       df_a['Volume_Imbalance_Up'], df_a['Volume_Imbalance_Down']):
            if vi_up:
                colors_vol.append('#06b6d4')   # Cyan = inyección institucional compradora
            elif vi_dn:
                colors_vol.append('#f59e0b')   # Amber = inyección institucional vendedora
            elif c >= o:
                colors_vol.append('#10b981')
            else:
                colors_vol.append('#ef4444')
    else:
        colors_vol = ['#10b981' if c >= o else '#ef4444' for c, o in zip(df_a['Close'], df_a['Open'])]

    fig.add_trace(go.Bar(
        x=df_a.index, y=df_a['Volume'],
        marker_color=colors_vol, marker_opacity=0.55, name='Volumen (🌊=Imbalance)', showlegend=False
    ), row=2, col=1)


    # RSI
    fig.add_trace(go.Scatter(
        x=df_a.index, y=df_a['RSI'],
        line=dict(color='#8b5cf6', width=1.5), name='RSI', showlegend=False
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(239,68,68,0.3)", row=3, col=1,
                  annotation_text="Sobrecomprado")
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(16,185,129,0.3)", row=3, col=1,
                  annotation_text="Sobrevendido")
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(148,163,184,0.03)", line_width=0, row=3, col=1)

    fig.update_layout(
        template='plotly_dark',
        height=600,
        margin=dict(l=0, r=10, t=25, b=10),
        xaxis_rangeslider_visible=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family='JetBrains Mono', size=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)", font=dict(size=9)
        ),
        hovermode='x unified'
    )
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.03)')
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.03)')

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown('''
    <div class="vol-legend">
        <span><div class="vol-dot" style="background:#06b6d4;"></div> Cyan = Imbalance Comprador Institucional (Fase 2)</span>
        <span><div class="vol-dot" style="background:#f59e0b;"></div> Amber = Imbalance Vendedor Institucional (Fase 2)</span>
        <span><div class="vol-dot" style="background:#10b981;"></div> Verde = Vela alcista normal</span>
        <span><div class="vol-dot" style="background:#ef4444;"></div> Rojo = Vela bajista normal</span>
    </div>
    ''', unsafe_allow_html=True)

    # ----- REASONING CONSOLE -----
    st.markdown('<div class="section-title">🧠 Razonamiento del Sistema v5.0</div>', unsafe_allow_html=True)
    st.markdown('<div class="help-text">Consola de decisión en tiempo real — [F1] Kill Switches · [F2] Volume Imbalance · [F3] Ensamble RF+GB Adaptativo</div>', unsafe_allow_html=True)


    r_lines = []
    # Escenario
    r_lines.append(("info", f"📍 Escenario: {scenario}"))

    # Score
    if score >= 70:
        r_lines.append(("bull", f"✅ Score {score}/100 — Señal FUERTE de compra. Múltiples indicadores alineados."))
    elif score >= 60:
        r_lines.append(("bull", f"📈 Score {score}/100 — Señal moderada de compra."))
    elif score <= 30:
        r_lines.append(("bear", f"⚠️ Score {score}/100 — Señal FUERTE de venta. Precaución."))
    elif score <= 40:
        r_lines.append(("bear", f"📉 Score {score}/100 — Señal moderada de venta."))
    else:
        r_lines.append(("", f"⏸️ Score {score}/100 — Zona neutral. Sin señal clara."))

    # RSI
    if rsi_val > 70:
        r_lines.append(("bear", f"📊 RSI {rsi_val:.0f} — Sobrecomprado. El precio podría retroceder."))
    elif rsi_val < 30:
        r_lines.append(("bull", f"📊 RSI {rsi_val:.0f} — Sobrevendido. Posible rebote alcista."))

    # Z-Score
    if z_score > 2.0:
        r_lines.append(("bear", f"⚡ Z-Score {z_score:.2f} — Desviación extrema ALTA. Posible corrección."))
    elif z_score < -2.0:
        r_lines.append(("bull", f"⚡ Z-Score {z_score:.2f} — Desviación extrema BAJA. Posible rebote."))

    # ML Ensamble RF+GB con peso dinámico (Fase 3)
    if ml_pred >= 70:
        r_lines.append(("ml", f"🤖 [F3] Ensamble RF+GB: {ml_pred}% prob. SUBIDA | Peso IA: {ml_dynamic_weight*100:.0f}% | Win-Rate rodante: {ml_rolling_acc*100:.0f}%"))
    elif ml_pred <= 30:
        r_lines.append(("ml", f"🤖 [F3] Ensamble RF+GB: {100-ml_pred}% prob. BAJA | Peso IA: {ml_dynamic_weight*100:.0f}% | Win-Rate rodante: {ml_rolling_acc*100:.0f}%"))
    else:
        r_lines.append(("ml", f"🤖 [F3] Ensamble RF+GB neutral ({ml_pred}%) | Peso IA: {ml_dynamic_weight*100:.0f}% (auto-calibrado)."))
    if ml_dynamic_weight <= 0.20:
        r_lines.append(("bear", "⚠️ [F3] Peso IA reducido automáticamente por baja precisión reciente (Model Decay). Prioridad: SMC técnico."))

    # SPY Sentiment
    if spy_sentiment == 1:
        r_lines.append(("bull", "🏛️ Mercado general ALCISTA (SPY EMA10 > EMA21)."))
    elif spy_sentiment == -1:
        r_lines.append(("bear", "🏛️ Mercado general BAJISTA (SPY EMA10 < EMA21). Señales de compra reducidas."))

    # VIX + Dynamic Threshold (IMP-3)
    macro_vix = df_a.attrs.get('macro_vix', 20)
    active_threshold = df_a.attrs.get('active_threshold', 65)
    r_lines.append(("info", f"📊 VIX: {macro_vix:.1f} — Umbral activo: {active_threshold}/100"))

    # HTF Daily Trend (IMP-4)
    htf_bias = df_a.attrs.get('htf_bias', 0)
    if htf_bias == 1:
        r_lines.append(("bull", "📈 HTF: ALCISTA — EMA20 diaria > EMA50 diaria. Tendencia mayor confirma."))
    elif htf_bias == -1:
        r_lines.append(("bear", "📉 HTF: BAJISTA — EMA20 diaria < EMA50 diaria. Tendencia mayor en contra."))

    # Fase 2: Volume Imbalance
    if vol_imbalance_up:
        r_lines.append(("bull", f"🌊 [F2] IMBALANCE COMPRADOR detectado — Volumen > 1.8x MA20. OB/FVG alcistas con +15/+5 pts de convicción extra."))
    elif vol_imbalance_dn:
        r_lines.append(("bear", f"🌊 [F2] IMBALANCE VENDEDOR detectado — Volumen > 1.8x MA20. OB/FVG bajistas con -15/-5 pts de convicción extra."))
    else:
        r_lines.append(("info", "🌊 [F2] Sin Imbalance institucional en la última vela. OB/FVG con puntuación estándar."))

    # Fase 1: Kill Switch y ATR Sizing
    if ks_daily:
        r_lines.append(("bear", "🚨 [F1] KILL SWITCH DIARIO ACTIVO — Pérdida del 3% alcanzada. Nuevas entradas BLOQUEADAS hasta mañana."))
    elif ks_weekly:
        r_lines.append(("bear", "🚨 [F1] KILL SWITCH SEMANAL ACTIVO — Pérdida del 5% semanal. Nuevas entradas BLOQUEADAS."))
    else:
        r_lines.append(("info", f"🛡️ [F1] Kill Switches: Normal | ATR Sizing activo — Tamaño ajustado por volatilidad ${atr_val:.2f}"))

    console_html = ""
    for cls, msg in r_lines:
        line_cls = f"reasoning-line-{cls}" if cls else "reasoning-line"
        console_html += f'<div class="reasoning-line {line_cls}"><span class="reasoning-timestamp">[{now_str}]</span> {msg}</div>'
    st.markdown(f'<div class="reasoning-console">{console_html}</div>', unsafe_allow_html=True)

else:
    st.warning(f"No hay datos suficientes para **{selected}**. Prueba con otro período o intervalo.")


# =============================================================================
# SCANNER GLOBAL — Escaneado de todo el portafolio
# =============================================================================
if btn_run or auto_scan:
    st.markdown("---")
    st.markdown('<div class="section-title">🔬 Scanner Global</div>', unsafe_allow_html=True)
    st.markdown('<div class="help-text">Analizando todas las acciones de tu watchlist para encontrar oportunidades.</div>', unsafe_allow_html=True)

    results = []
    bar = st.progress(0, text="Iniciando análisis...")
    for idx, t in enumerate(tickers_list):
        bar.progress((idx + 1) / len(tickers_list), text=f"Analizando {t}...")
        if idx > 0:
            time.sleep(0.15)
        try:
            d_s = get_stock_data(t, period=period, interval=interval)
            if not d_s.empty and len(d_s) >= 50:
                da_s = apply_strategy(d_s, spy_sentiment=spy_sentiment, ticker_symbol=t)
                t_score = int(da_s['Score'].iloc[-1])
                t_price = float(da_s['Close'].iloc[-1])
                t_ml = da_s.attrs.get('ml_prediction', 50)

                if t_score >= 65:
                    t_signal = "🟢 COMPRAR"
                elif t_score <= 35:
                    t_signal = "🔴 VENDER"
                else:
                    t_signal = "⚪ ESPERAR"

                results.append({
                    "Ticker": t,
                    "Precio": f"${t_price:,.2f}",
                    "Score": t_score,
                    "Señal": t_signal,
                    "IA": f"{t_ml}%"
                })
            elif d_s.empty:
                results.append({
                    "Ticker": t,
                    "Precio": "N/A",
                    "Score": 0,
                    "Señal": "⚠️ Sin datos",
                    "IA": "N/A"
                })
            else:
                results.append({
                    "Ticker": t,
                    "Precio": "N/A",
                    "Score": 0,
                    "Señal": "⚠️ Datos Insuficientes",
                    "IA": "N/A"
                })
        except Exception as e:
            logger.exception(f"Error analizando ticker {t}")
            results.append({
                "Ticker": t,
                "Precio": "Error",
                "Score": 0,
                "Señal": f"❌ {type(e).__name__}",
                "IA": "N/A"
            })
    bar.empty()

    if results:
        df_res = pd.DataFrame(results).sort_values(by='Score', ascending=False)
        st.dataframe(
            df_res,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", help="Puntuación de 0-100",
                    min_value=0, max_value=100, format="%d"
                ),
            }
        )
    else:
        st.info("No se encontraron resultados. Verifica tu conexión a internet.")


# =============================================================================
# TABS: Portfolio, Historial, Conexión
# =============================================================================
st.markdown("---")
tab1, tab2, tab3 = st.tabs(["📊 Portfolio en Vivo", "📜 Historial de Trades", "🔗 Estado del Sistema"])

with tab1:
    st.markdown('<div class="section-title">Posiciones Abiertas</div>', unsafe_allow_html=True)
    try:
        bc = get_broker_client()
        if bc:
            if bc.is_connected():
                acc = bc.get_account_info()
                if acc:
                    a1, a2, a3 = st.columns(3)
                    with a1:
                        st.metric("💵 Capital Total", f"${acc['equity']:,.2f}")
                    with a2:
                        st.metric("💳 Poder de Compra", f"${acc['buying_power']:,.2f}")
                    with a3:
                        st.metric("📊 Estado", acc['status'])

                positions = bc.get_open_positions()
                if positions:
                    df_pos = pd.DataFrame(positions)
                    df_pos['unrealized_pl'] = df_pos['unrealized_pl'].apply(lambda x: f"${x:+,.2f}")
                    df_pos['unrealized_plpc'] = df_pos['unrealized_plpc'].apply(lambda x: f"{x:+.2f}%")
                    df_pos['current_price'] = df_pos['current_price'].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(df_pos[['symbol', 'qty', 'current_price', 'unrealized_pl', 'unrealized_plpc', 'side']],
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("No hay posiciones abiertas actualmente.")
            else:
                st.warning("No se pudo conectar con Alpaca. Verifica tus credenciales.")
        else:
            st.info("Configura tus credenciales de Alpaca (.env) para ver el portfolio en vivo.")
    except Exception as e:
        st.error(f"Error conectando con Alpaca: {e}")

with tab2:
    st.markdown('<div class="section-title">Últimas Operaciones</div>', unsafe_allow_html=True)
    hist = get_trade_history()
    if not hist.empty:
        st.dataframe(hist, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han registrado operaciones. Activa el Auto-Bot para comenzar.")

with tab3:
    st.markdown('<div class="section-title">Estado del Sistema</div>', unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1:
        market_status = "🟢 Abierto" if m_open else "🔴 Cerrado"
        st.metric("Mercado", market_status)
    with s2:
        st.metric("Scanner", "🟢 Activo" if auto_scan else "⚪ Inactivo")
    with s3:
        st.metric("Auto-Bot", "🟢 Trading" if auto_trade else "⚪ Apagado")

    s4, s5, s6, s7 = st.columns(4)
    with s4:
        try:
            _bc = get_broker_client()
            if _bc:
                open_count = len(_bc.get_open_positions()) if _bc.is_connected() else 0
            else:
                open_count = 0
        except Exception:
            open_count = 0
        st.metric("Posiciones Abiertas", f"{open_count}/{TradingBrain.MAX_CONCURRENT_POSITIONS}")
    with s5:
        daily_status = "🔴 ACTIVO" if config.get("daily_loss_breaker", False) else "🟢 Normal"
        weekly_status = "🔴 ACTIVO" if config.get("weekly_loss_breaker", False) else "🟢 Normal"
        st.metric("🛑 Kill Switch Diario (F1)", daily_status,
                  help="Se activa si la pérdida del día supera el 3% de la equidad.")
    with s6:
        st.metric("🛑 Kill Switch Semanal (F1)", weekly_status,
                  help="Se activa si la pérdida de la semana supera el 5% de la equidad.")
    with s7:
        try:
            _acc, _wt = calculate_ml_rolling_accuracy()
            wt_label = f"{_acc*100:.0f}% WR · Peso {_wt*100:.0f}%"
        except Exception:
            wt_label = "Sin datos"
        st.metric("🤖 IA Adaptativa (F3)", wt_label,
                  help="Win-Rate real de los últimos 15 trades y peso dinámico asignado al Ensamble RF+GB.")


    # Cache stats
    try:
        from core.data_fetcher import get_cache_stats
        stats = get_cache_stats()
        st.markdown(f'<div class="help-text">Cache de datos: {stats["total_entries"]} entradas ({stats["fresh"]} frescas, {stats["stale"]} expiradas)</div>', unsafe_allow_html=True)
    except Exception:
        pass

    st.markdown("---")
    # Verificar si el worker está vivo
    try:
        import requests
        resp = requests.get("http://localhost:8001/health", timeout=1)
        if resp.status_code == 200:
            hdata = resp.json()
            st.success(f"🟢 Worker activo | Uptime: {hdata['uptime_seconds']//3600}h {(hdata['uptime_seconds']%3600)//60}m")
        else:
            st.warning("⚠️ Worker respondió con error")
    except Exception:
        st.error("🔴 Worker no detectado en localhost:8001")

    st.markdown(f'<div class="help-text">Última actualización: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>', unsafe_allow_html=True)
