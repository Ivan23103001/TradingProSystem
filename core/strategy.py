import pandas as pd
import ta
import numpy as np
try:
    from .ml_engine import get_ml_prediction
except (ImportError, ValueError):
    try:
        from ml_engine import get_ml_prediction
    except ImportError:
        get_ml_prediction = None

def apply_strategy(df):
    """
    Motor Matemático (Precisión Mejorada).
    Implementa un sistema de Puntuación (Score 0-100) basado en la confluencia de
    múltiples indicadores profesionales: RSI, MACD, Bandas de Bollinger, Estocástico y EMAs.
    """
    if df.empty or len(df) < 50:
        res = df.copy()
        for col in ['RSI', 'Score', 'Signal', 'Stoch_K', 'MACD', 'MACD_Signal', 'MACD_Hist']:
            res[col] = 50 if col in ['RSI', 'Score', 'Stoch_K'] else 0
        for col in ['EMA_20', 'EMA_50', 'BB_High', 'BB_Low', 'BB_Mid']:
            res[col] = res['Close'] if not res.empty else 0
        return res
        
    data = df.copy()
    
    # 1. Indicadores de Momentum
    data['RSI'] = ta.momentum.RSIIndicator(close=data['Close'], window=14).rsi()
    stoch = ta.momentum.StochasticOscillator(high=data['High'], low=data['Low'], close=data['Close'], window=14, smooth_window=3)
    data['Stoch_K'] = stoch.stoch()
    
    # 2. Indicadores de Tendencia
    macd = ta.trend.MACD(close=data['Close'])
    data['MACD'] = macd.macd()
    data['MACD_Signal'] = macd.macd_signal()
    data['MACD_Hist'] = macd.macd_diff()
    
    data['EMA_20'] = ta.trend.EMAIndicator(close=data['Close'], window=20).ema_indicator()
    data['EMA_50'] = ta.trend.EMAIndicator(close=data['Close'], window=50).ema_indicator()
    
    # 3. Ondas de Volatilidad (Bollinger)
    bb = ta.volatility.BollingerBands(close=data['Close'], window=20, window_dev=2)
    data['BB_High'] = bb.bollinger_hband()
    data['BB_Low'] = bb.bollinger_lband()
    data['BB_Mid'] = bb.bollinger_mavg()
    
    # 4. Volumen (Volume Profile simplificado)
    if 'Volume' in data.columns:
        data['Volume_SMA'] = ta.trend.sma_indicator(data['Volume'], window=20)
    
    signals = []
    scores = []
    
    # Sistema de Puntuación Predictiva (Backend Precision Engine)
    for i in range(len(data)):
        if i < 35:
            signals.append(0)
            scores.append(50)
            continue
            
        score = 50 # Base neutral (50/100)
        
        # A. MOMENTUM (Fuerza del Movimiento)
        rsi = data['RSI'].iloc[i]
        if rsi < 40: score += 15       # Barato
        if rsi < 30: score += 15       # Muy Barato (Sobrevendido)
        if rsi > 60: score -= 15       # Caro
        if rsi > 70: score -= 15       # Muy Caro (Sobrecomprado)
        
        stoch_k = data['Stoch_K'].iloc[i]
        if stoch_k < 20: score += 10   # Rebote inminente al alza
        if stoch_k > 80: score -= 10   # Corrección inminente a la baja
        
        # B. TENDENCIA Y ACELERACIÓN (MACD)
        macd_hist = data['MACD_Hist'].iloc[i]
        macd_hist_prev = data['MACD_Hist'].iloc[i-1]
        
        if macd_hist > 0 and macd_hist_prev <= 0: score += 20     # Cruce Alcista (Oro)
        elif macd_hist < 0 and macd_hist_prev >= 0: score -= 20   # Cruce Bajista (Muerte)
        
        if macd_hist > macd_hist_prev: score += 5                 # Acelerando hacia arriba
        elif macd_hist < macd_hist_prev: score -= 5               # Acelerando hacia abajo
            
        # C. VOLATILIDAD EXTREMA (Bollinger)
        precio = data['Close'].iloc[i]
        bb_low = data['BB_Low'].iloc[i]
        bb_high = data['BB_High'].iloc[i]
        
        if precio <= bb_low: score += 20   # Fuera de la banda inferior (Pánico = Oportunidad)
        if precio >= bb_high: score -= 20  # Fuera de la banda superior (Euforia = Peligro)
            
        # D. MACRO TENDENCIA (Medias Móviles)
        if data['EMA_20'].iloc[i] > data['EMA_50'].iloc[i]: score += 5  # Tendencia general positiva
        else: score -= 5                                                # Tendencia general negativa
            
        # E. VOLUMEN PROFUNDO (Volume Profile)
        if 'Volume' in data.columns and 'Volume_SMA' in data.columns:
            vol_actual = data['Volume'].iloc[i]
            vol_sma = data['Volume_SMA'].iloc[i]
            open_p = data['Open'].iloc[i]
            if vol_actual > (vol_sma * 1.5): # Volumen excepcionalmente alto
                if precio > open_p: score += 10  # Volumen alto impulsando compra
                else: score -= 10                # Volumen alto impulsando venta
                
        # Normalizar y guardar score manual
        score = max(0, min(100, score))
        
        # FASE 8: INTEGRACIÓN MACHINE LEARNING (Ponderación Inteligente)
        final_score = score
        if get_ml_prediction and i == len(data) - 1:
            ml_prob = get_ml_prediction(data.iloc[:i+1])
            # El Score final es 70% Reglas Técnicas + 30% Predicción IA
            final_score = (score * 0.7) + (ml_prob * 0.3)
            
        scores.append(int(final_score))
        
        # VEREDICTO FINAL DE PRECISIÓN (Lógica de salida mejorada)
        if final_score >= 80:
            signals.append(1) # Compra Excepcional
        elif final_score <= 20:
            signals.append(-1) # Venta de pánico
        elif final_score <= 35:
            signals.append(-0.75) # Liquidación fuerte
        elif final_score <= 45:
            signals.append(-0.5) # Toma de ganancias parcial
        else:
            signals.append(0)
            
    data['Signal'] = signals
    data['Score'] = scores
    return data
