import pandas as pd
import ta
import numpy as np
import sqlite3
import os
from .brain import TradingBrain

try:
    from .ml_engine import get_ml_prediction, calculate_ml_rolling_accuracy
except (ImportError, ValueError):
    try:
        from ml_engine import get_ml_prediction, calculate_ml_rolling_accuracy
    except ImportError:
        get_ml_prediction = None
        calculate_ml_rolling_accuracy = None

import threading

_macro_cache = {"data": None, "ts": 0}
_htf_cache = {}   # {ticker_symbol: {"bias": int, "ts": float}}
_htf_cache_lock = threading.Lock()  # Protege acceso concurrente desde múltiples hilos
_HTF_CACHE_MAX = 150  # Límite para evitar crecimiento indefinido en VPS 24/7

def _safe(val, default=0.0):
    """Devuelve el valor si no es NaN, de lo contrario devuelve default."""
    try:
        if pd.notna(val):
            return float(val)
    except Exception:
        pass
    return default

def get_spy_sentiment():
    """
    Obtiene el sentimiento del mercado general (SPY) para filtrar señales.
    v4.1: Versión optimizada con EMAs rápidas (10/21) para detectar cambios institucionales.
    """
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY").history(period="1mo", interval="1d")
        if spy.empty or len(spy) < 21:
            return 0 
        ema10 = ta.trend.ema_indicator(spy['Close'], window=10)
        ema21 = ta.trend.ema_indicator(spy['Close'], window=21)
        last_ema10 = _safe(ema10.iloc[-1])
        last_ema21 = _safe(ema21.iloc[-1])
        
        if last_ema10 > last_ema21:
            return 1 # Bullish rápido
        else:
            return -1 # Bearish rápido
    except Exception:
        return 0

def detect_liquidity_sweeps(df):
    """
    Detección de Liquidity Sweeps (Caza de Stops).
    """
    params = TradingBrain.get_technical_params()
    lookback = params["smc_lookback"]
    wick_ratio = params["smc_wick"]
    
    df['Local_High'] = df['High'].shift(1).rolling(window=lookback).max()
    df['Local_Low'] = df['Low'].shift(1).rolling(window=lookback).min()
    
    # Bearish Sweep
    df['Is_Bearish_Sweep'] = (df['High'] > df['Local_High']) & (df['Close'] < df['Local_High'])
    df['Wick_Ratio_Up'] = (df['High'] - df['Close']) / (df['High'] - df['Low'] + 1e-9)
    df['Bearish_Sweep_Signal'] = (df['Is_Bearish_Sweep'] & (df['Wick_Ratio_Up'] > wick_ratio)).astype(float)
    
    # Bullish Sweep
    df['Is_Bullish_Sweep'] = (df['Low'] < df['Local_Low']) & (df['Close'] > df['Local_Low'])
    df['Wick_Ratio_Down'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'] + 1e-9)
    df['Bullish_Sweep_Signal'] = (df['Is_Bullish_Sweep'] & (df['Wick_Ratio_Down'] > wick_ratio)).astype(float)
    
    return df

def detect_order_blocks(df):
    """
    Identifica Order Blocks (OB) Institucionales.
    """
    params = TradingBrain.get_technical_params()
    atr_mult = params["smc_atr"]
    
    df['Body_Size'] = (df['Close'] - df['Open']).abs()
    df['Range'] = df['High'] - df['Low']
    df['ATR_14'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
    
    # Displacement: Vela que rompe con fuerza (Cuerpo > ATR * Multiplier del CEREBRO)
    df['Displacement_Up'] = (df['Close'] > df['Open']) & (df['Body_Size'] > df['ATR_14'] * atr_mult)
    df['Displacement_Down'] = (df['Close'] < df['Open']) & (df['Body_Size'] > df['ATR_14'] * atr_mult)
    
    df['Bullish_OB'] = df['Low'].shift(1).where(df['Displacement_Up'], 0.0).fillna(0.0)
    df['Bearish_OB'] = df['High'].shift(1).where(df['Displacement_Down'], 0.0).fillna(0.0)
    return df


def detect_volume_imbalances(df):
    """
    Identifica Imbalances de Volumen (Volume Imbalances) e interés institucional.
    Se da cuando hay un desplazamiento con un volumen sustancialmente mayor al promedio de 20 velas.
    """
    params = TradingBrain.get_technical_params()
    vol_mult = params.get("smc_vol_mult", 1.8)
    
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Imbalance_Up'] = (df['Close'] > df['Open']) & (df['Volume'] > df['Vol_MA20'] * vol_mult)
    df['Volume_Imbalance_Down'] = (df['Close'] < df['Open']) & (df['Volume'] > df['Vol_MA20'] * vol_mult)
    return df

def detect_fvg(df):
    """
    Detecta Fair Value Gaps (FVG) institucionales.
    """
    df['FVG_Bullish'] = 0.0
    df['FVG_Bearish'] = 0.0
    
    # FVG Alcista: Low actual > High de hace 2 velas
    bullish_gap = (df['Low'] > df['High'].shift(2)) & (df['Close'] > df['Open'])
    # FVG Bajista: High actual < Low de hace 2 velas
    bearish_gap = (df['High'] < df['Low'].shift(2)) & (df['Close'] < df['Open'])
    
    df.loc[bullish_gap, 'FVG_Bullish'] = df['High'].shift(2) # Nivel superior del gap
    df.loc[bearish_gap, 'FVG_Bearish'] = df['Low'].shift(2) # Nivel inferior del gap
    return df

def detect_breakers(df):
    """
    Identifica Breaker Blocks (Inversión de Estructura).
    Un Order Block anterior que falló tras un barrido de liquidez.
    """
    params = TradingBrain.get_technical_params()
    breaker_mult = params["smc_breaker"]
    
    bearish_ob_prev = df['Bearish_OB'].shift(1)
    high_prev = df['High'].shift(1)
    bullish_breaker_cond = (bearish_ob_prev > 0) & (df['Close'] > bearish_ob_prev * breaker_mult)
    df['Bullish_Breaker'] = high_prev.where(bullish_breaker_cond, 0.0).fillna(0.0)
    
    bullish_ob_prev = df['Bullish_OB'].shift(1)
    low_prev = df['Low'].shift(1)
    bearish_breaker_cond = (bullish_ob_prev > 0) & (df['Close'] < bullish_ob_prev / breaker_mult)
    df['Bearish_Breaker'] = low_prev.where(bearish_breaker_cond, 0.0).fillna(0.0)
    return df

def get_macro_regime():
    """
    Obtiene el estado macro del mercado usando VIX y DXY.
    Cache de 300s para evitar llamadas repetidas por cada ticker/vela.
    """
    import time
    global _macro_cache
    now = time.time()
    if _macro_cache["data"] is not None and (now - _macro_cache["ts"]) < 300:
        return _macro_cache["data"]
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").history(period="5d", interval="1d")
        dxy = yf.Ticker("DX-Y.NYB").history(period="5d", interval="1d")

        last_vix = vix['Close'].iloc[-1] if not vix.empty else 20.0
        # Tendencia del DXY
        dxy_trend = 1 if not dxy.empty and dxy['Close'].iloc[-1] > dxy['Close'].iloc[-2] else -1

        result = {"vix": last_vix, "dxy_trend": dxy_trend}
    except Exception:
        result = {"vix": 20.0, "dxy_trend": 0}
    _macro_cache["data"] = result
    _macro_cache["ts"] = now
    return result

def calculate_volume_profile(df, lookback=50):
    """
    Calcula dinámicamente el Point of Control (POC) local del Volume Profile.
    v5.3: Usa sliding_window_view de numpy — evita rolling().apply() por completo,
    eliminando incompatibilidades de dimensión entre versiones de pandas.
    Encuentra el precio con mayor volumen acumulado en cada ventana móvil.
    """
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view

    closes = df['Close'].round(2).values
    volumes = df['Volume'].values
    n = len(closes)

    if n < lookback:
        df['POC'] = df['Close']
        return df

    # Ventanas deslizantes vectorizadas: (n - lookback + 1, lookback)
    price_windows = sliding_window_view(closes, lookback)
    vol_windows = sliding_window_view(volumes, lookback)

    poc_values = np.full(n, np.nan)

    for i in range(len(price_windows)):
        win_prices = price_windows[i]
        win_vols = vol_windows[i]

        # Precio con mayor volumen acumulado en la ventana
        unique_p = np.unique(win_prices)
        best_price = float(win_prices[-1])
        best_vol = -1.0
        for p in unique_p:
            total_vol = win_vols[win_prices == p].sum()
            if total_vol > best_vol:
                best_vol = total_vol
                best_price = float(p)

        poc_values[lookback - 1 + i] = best_price

    # Construir Series y forward-fill los NaN iniciales
    poc_series = pd.Series(poc_values, index=df.index).ffill().fillna(df['Close'])
    df['POC'] = poc_series
    return df

def calculate_kelly_criterion(db_path='trade_history.db'):
    """
    Calcula el Criterio de Kelly fraccionario basado en el historial real.
    f* = (p * b - q) / b
    
    v5.3: Normaliza PnL a porcentaje (pnl / cantidad) para evitar sesgo
    por diferencias en tamaño de posición (notional).
    """
    try:
        if not os.path.exists(db_path):
            return 0.15 
            
        from .database import get_connection
        conn = get_connection(db_path)
        df_trades = pd.read_sql_query(
            "SELECT pnl, cantidad FROM trades WHERE pnl IS NOT NULL", conn
        )
        # No cerrar: la conexión pertenece al pool thread-local
        
        if len(df_trades) < 5:
            return 0.15
        
        # Normalizar PnL a porcentaje: dividir por el notional (guardado en 'cantidad')
        df_trades['pnl_pct'] = df_trades['pnl'] / df_trades['cantidad'].abs()
            
        wins = df_trades[df_trades['pnl_pct'] > 0]['pnl_pct']
        losses = df_trades[df_trades['pnl_pct'] <= 0]['pnl_pct'].abs()
        
        if len(losses) == 0: return 0.2
        
        p = len(wins) / len(df_trades)
        q = 1 - p
        avg_win = wins.mean() if not wins.empty else 1
        avg_loss = losses.mean() if not losses.empty else 1
        b = avg_win / (avg_loss + 1e-9)
        
        kelly = (p * b - q) / (b + 1e-9)
        return max(0.05, min(0.25, kelly * 0.5))
    except Exception:
        return 0.15

def calculate_var(df, confidence=0.95):
    """Calcula el Value at Risk (VaR) paramétrico."""
    returns = df['Close'].pct_change().dropna()
    if returns.empty: return 0.02
    mu = returns.mean()
    sigma = returns.std()
    # VaR simple sin scipy para evitar dependencias extra si no estuviera
    var = mu - (1.645 * sigma) if confidence == 0.95 else mu - (2.33 * sigma)
    return abs(var)

from typing import Optional, List, Dict, Any, Tuple

def apply_strategy(df: pd.DataFrame, spy_sentiment: Optional[int] = None, ticker_symbol: Optional[str] = None) -> pd.DataFrame:
    """
    Motor Cuantitativo v4.2 (ML Ensemble Revolution).
    Ensamble de Heurísticas + OB + Sweeps + ML Prediction + Dynamic Risk.
    """
    if df.empty or len(df) < 50:
        return df
        
    data = df.copy()
    
    # 1. Sentimiento General
    if spy_sentiment is None:
        spy_sentiment = get_spy_sentiment()
    
    # 2. Indicadores Estándar
    data['Daily_Return'] = data['Close'].pct_change()
    data['EMA_20'] = ta.trend.ema_indicator(data['Close'], window=20)
    data['EMA_50'] = ta.trend.ema_indicator(data['Close'], window=50)
    data['EMA_200'] = ta.trend.ema_indicator(data['Close'], window=200)
    data['RSI'] = ta.momentum.RSIIndicator(data['Close']).rsi()
    data['ATR'] = ta.volatility.average_true_range(data['High'], data['Low'], data['Close'])
    
    # 3. Z-Score Acelerado
    data['SMA_20'] = data['Close'].rolling(window=20).mean()
    data['Std_20'] = data['Close'].rolling(window=20).std()
    data['Z_Score'] = (data['Close'] - data['SMA_20']) / (data['Std_20'] + 1e-9)
    
    # 4. Trend Health (Pendiente EMA 200 + Momentum)
    data['EMA_200_Slope'] = data['EMA_200'].diff(5)
    data['Trend_Health'] = (data['EMA_200_Slope'] > 0) & (data['RSI'] > 50)
    
    # 5. Microestructura Institucional
    data = detect_liquidity_sweeps(data)
    data = detect_order_blocks(data)
    data = detect_volume_imbalances(data)
    data = detect_fvg(data)
    data = detect_breakers(data)
    data = calculate_volume_profile(data)
    
    data['Dist_POC'] = (data['Close'] - data['POC']) / (data['Close'] + 1e-9)
    
    # 6. Indicadores Avanzados para ML (Features que el Random Forest espera)
    try:
        stoch = ta.momentum.StochasticOscillator(data['High'], data['Low'], data['Close'])
        data['Stoch_K'] = stoch.stoch()
        macd_ind = ta.trend.MACD(data['Close'])
        data['MACD'] = macd_ind.macd()
        data['MACD_Hist'] = macd_ind.macd_diff()
        data['ADX'] = ta.trend.ADXIndicator(data['High'], data['Low'], data['Close']).adx()
        data['ROC'] = ta.momentum.ROCIndicator(data['Close']).roc()
        data['MFI'] = ta.volume.MFIIndicator(data['High'], data['Low'], data['Close'], data['Volume']).money_flow_index()
        data['CMF'] = ta.volume.ChaikinMoneyFlowIndicator(data['High'], data['Low'], data['Close'], data['Volume']).chaikin_money_flow()
        data['Std_Dev'] = data['Close'].rolling(window=20).std()
        rolling_ret = data['Daily_Return'].rolling(window=20)
        data['Sharpe_Ratio'] = (rolling_ret.mean() / (rolling_ret.std() + 1e-9)) * np.sqrt(252)
        data['Beta'] = data['Daily_Return'].rolling(window=20).std() / (data['Daily_Return'].rolling(window=60).std() + 1e-9)
    except Exception:
        pass  # Si algun indicador falla, el ML se degrada a neutro (50)
    
    # 7. Prediccion ML (una sola vez para todo el DataFrame)
    ml_prediction = 50  # Neutro por defecto
    if get_ml_prediction is not None:
        try:
            ml_prediction = get_ml_prediction(data)
        except Exception:
            ml_prediction = 50
    
    signals = []
    scores = []
    scenarios = []

    kelly_size = calculate_kelly_criterion()
    macro_regime = get_macro_regime()
    params = TradingBrain.get_technical_params()

    # IMP-3: Dynamic VIX Threshold (calculado una vez; VIX es el mismo para todas las velas)
    vix_level = macro_regime.get("vix", 20)
    threshold = next((t for vmax, t in TradingBrain.VIX_SCORE_THRESHOLDS if vix_level < vmax), 75)

    # IMP-4: HTF Daily Trend Confirmation
    htf_bias = 0  # 0 = neutral, 1 = alcista, -1 = bajista
    if ticker_symbol:
        import time as _time
        with _htf_cache_lock:
            cached_htf = _htf_cache.get(ticker_symbol, {})
        if cached_htf and (_time.time() - cached_htf.get("ts", 0)) < 3600:
            htf_bias = cached_htf["bias"]
        else:
            try:
                import yfinance as yf
                daily_df = yf.Ticker(ticker_symbol).history(period="3mo", interval="1d")
                if not daily_df.empty and len(daily_df) >= 50:
                    ema20_d = ta.trend.ema_indicator(daily_df['Close'], window=20)
                    ema50_d = ta.trend.ema_indicator(daily_df['Close'], window=50)
                    htf_bias = 1 if _safe(ema20_d.iloc[-1]) > _safe(ema50_d.iloc[-1]) else -1
                    with _htf_cache_lock:
                        _htf_cache[ticker_symbol] = {"bias": htf_bias, "ts": _time.time()}
                else:
                    with _htf_cache_lock:
                        _htf_cache[ticker_symbol] = {"bias": 0, "ts": _time.time()}
            except Exception:
                htf_bias = 0
                with _htf_cache_lock:
                    _htf_cache[ticker_symbol] = {"bias": 0, "ts": _time.time()}

    # Limpieza: evitar crecimiento indefinido en VPS (máx 150 tickers)
    with _htf_cache_lock:
        if len(_htf_cache) > _HTF_CACHE_MAX:
            # Eliminar las entradas más antiguas (por timestamp) para volver al límite
            sorted_keys = sorted(_htf_cache, key=lambda k: _htf_cache[k].get("ts", 0))
            keys_to_remove = sorted_keys[:len(_htf_cache) - _HTF_CACHE_MAX]
            for k in keys_to_remove:
                del _htf_cache[k]
    bull_ob_win = data['Bullish_OB'].rolling(window=20, min_periods=1).max().shift(1)
    bear_ob_win = data['Bearish_OB'].rolling(window=20, min_periods=1).min().shift(1)
    bull_fvg_win = data['FVG_Bullish'].rolling(window=10, min_periods=1).max().shift(1)
    bear_fvg_win = data['FVG_Bearish'].rolling(window=10, min_periods=1).min().shift(1)
    
    vol_imb_up_20 = data['Volume_Imbalance_Up'].rolling(window=20, min_periods=1).max().shift(1) > 0
    vol_imb_down_20 = data['Volume_Imbalance_Down'].rolling(window=20, min_periods=1).max().shift(1) > 0
    vol_imb_up_10 = data['Volume_Imbalance_Up'].rolling(window=10, min_periods=1).max().shift(1) > 0
    vol_imb_down_10 = data['Volume_Imbalance_Down'].rolling(window=10, min_periods=1).max().shift(1) > 0
    
    # Formateo de tiempos indexados una sola vez (vectorizado)
    if hasattr(data.index, 'strftime'):
        formatted_times = data.index.strftime("%H:%M")
    else:
        formatted_times = ["00:00"] * len(data)
    
    # Calcular precisión real de IA fuera de la iteración (una sola vez) para ahorrar accesos redundantes a DB
    ml_weight = 0.40  # fallback estándar
    if ml_prediction != 50:
        if calculate_ml_rolling_accuracy:
            try:
                _, ml_weight = calculate_ml_rolling_accuracy()
            except Exception:
                ml_weight = 0.40

    for i in range(len(data)):
        if i < 50:
            signals.append(0.0); scores.append(50); scenarios.append("Calibrando...")
            continue
            
        precio = data['Close'].iloc[i]
        current_scenario = "Estándar"
        score = 50.0
        
        # A. Lógica Institucional: OB, FVG y POC (Uso de pre-calculados rodantes en O(1))
        bull_ob = bull_ob_win.iloc[i]
        bear_ob = bear_ob_win.iloc[i]
        bull_fvg = bull_fvg_win.iloc[i]
        bear_fvg = bear_fvg_win.iloc[i]
        poc = data['POC'].iloc[i]
        
        if bull_ob > 0 and precio <= bull_ob * 1.005 and precio >= bull_ob:
            score += 20; current_scenario = "🎯 OB Alcista"
            # Confluencia de Imbalance de Volumen (Order Flow Institucional)
            if vol_imb_up_20.iloc[i]:
                score += 15; current_scenario += " + Vol Imbalance"
        elif bear_ob > 0 and precio >= bear_ob * 0.995 and precio <= bear_ob:
            score -= 20; current_scenario = "🎯 OB Bajista"
            # Confluencia de Imbalance de Volumen (Order Flow Institucional)
            if vol_imb_down_20.iloc[i]:
                score -= 15; current_scenario += " + Vol Imbalance"
            
        if bull_fvg > 0 and (precio <= bull_fvg * 1.01 and precio >= bull_fvg * 0.99):
            score += 15; current_scenario = "🧲 FVG Alcista"
            # Si el FVG coincide con volumen fuerte en el bloque, aumenta precisión
            if vol_imb_up_10.iloc[i]:
                score += 5; current_scenario += " + Strong Vol"
            if poc > 0 and abs((precio - poc) / poc) < 0.01:
                score += 10; current_scenario += " + POC"
        elif bear_fvg > 0 and (precio >= bear_fvg * 0.99 and precio <= bear_fvg * 1.01):
            score -= 15; current_scenario = "🧲 FVG Bajista"
            # Si el FVG coincide con volumen fuerte en el bloque, aumenta precisión
            if vol_imb_down_10.iloc[i]:
                score -= 5; current_scenario += " + Strong Vol"
            if poc > 0 and abs((precio - poc) / poc) < 0.01:
                score -= 10; current_scenario += " + POC"
                
        if "POC" not in current_scenario and poc > 0:
            if precio > poc and data['Close'].iloc[i-1] <= poc:
                 score += 10; current_scenario = "🔋 Ruptura POC"
            elif precio < poc and data['Close'].iloc[i-1] >= poc:
                 score -= 10; current_scenario = "🪫 Ruptura POC"
            
        # B. Lógica de Sweeps & Judas Swing
        is_judas = False
        bar_vix = macro_regime["vix"]
        dxy_bullish = macro_regime["dxy_trend"] > 0
        
        if data['Bearish_Sweep_Signal'].iloc[i] > 0:
            score -= 30; current_scenario = "🧹 Bearish Sweep"
        elif data['Bullish_Sweep_Signal'].iloc[i] > 0:
            score += 30; current_scenario = "🧹 Bullish Sweep"
            # Si el sweep ocurre al inicio de sesión (9:30 - 10:30), es un Judas Swing
            current_hhmm = formatted_times[i]
            if "09:30" <= current_hhmm <= "10:30":
                score += 15; current_scenario = "🤡 Judas Swing Alcista"
                is_judas = True
            
        # C. Silver Bullet Window
        current_hhmm = formatted_times[i]
        if TradingBrain.is_silver_bullet_time(current_hhmm):
            score = score * 1.25 if score > 50 else score * 0.75
            current_scenario += " ⏱️ Silver Bullet"
 
        # D. Breakers (Inversión de Poder)
        if data['Bullish_Breaker'].iloc[i] > 0:
             score += 25; current_scenario = "⚡ Bullish Breaker"
        elif data['Bearish_Breaker'].iloc[i] > 0:
             score -= 25; current_scenario = "⚡ Bearish Breaker"
 
        # E. Filtros Macro (Cerebro)
        if bar_vix > params["vix_max"]:
             # Pánico total: Reducir drasticamente score de compra y potenciar venta
             if score > 50: score = 50 + (score - 50) * 0.2
             else: score = 50 + (score - 50) * 1.5
             current_scenario += " ⛈️ Filtro VIX: Pánico"
         
        if dxy_bullish and score > 50:
             # DXY Fuerte: Las acciones sufren, reducir convicción de compra
             score = 50 + (score - 50) * params["dxy_red"]
             current_scenario += " 💵 Filtro DXY: Risk-Off"
            
        # F. ML Ensemble: Mezcla heurística autoadaptativa por precisión
        if ml_prediction != 50:  # ML tiene opinión (no neutro)
            tech_weight = 1.0 - ml_weight
            score = (score * tech_weight) + (ml_prediction * ml_weight)
            if ml_prediction >= 75:
                current_scenario += f" + 🤖 ML Bullish (W:{ml_weight*100:.0f}%)"
            elif ml_prediction <= 25:
                current_scenario += f" + 🤖 ML Bearish (W:{ml_weight*100:.0f}%)"
            
        # G. HTF Daily Trend Confirmation (IMP-4)
        if htf_bias == -1 and score > 50:
            score = 50 + (score - 50) * 0.3
            current_scenario += " 📉 HTF: BAJISTA"
        elif htf_bias == 1 and score < 50:
            score = 50 + (score - 50) * 0.3
            current_scenario += " 📈 HTF: ALCISTA"
 
        # H. Dynamic VIX Threshold (IMP-3)
        final_score = float(max(0, min(100, score)))
        scores.append(int(final_score))
        scenarios.append(current_scenario)
 
        if final_score >= threshold: signals.append(1.0)
        elif final_score <= (100 - threshold): signals.append(-1.0)
        else: signals.append(0.0)
        
    data['Signal'] = signals
    data['Score'] = scores
    data['Market_Scenario'] = scenarios
    data.attrs['kelly_size'] = kelly_size
    data.attrs['ml_prediction'] = ml_prediction
    data.attrs['macro_vix'] = vix_level
    data.attrs['active_threshold'] = threshold
    data.attrs['htf_bias'] = htf_bias
    
    return data
