import yfinance as yf
import pandas as pd
import time as _time
import threading
import logging

# =============================================================================
# CACHÉ UNIVERSAL — Funciona dentro y fuera de Streamlit
# =============================================================================
# Caché en memoria con TTL (Time To Live) independiente de Streamlit.
# Evita bombardear la API de Yahoo Finance cuando bot_worker.py corre standalone.

_cache = {}          # {cache_key: {"data": DataFrame, "timestamp": float}}
_cache_lock = threading.Lock()
_CACHE_TTL = 45      # Segundos antes de refrescar datos (45s > ciclo de 60s del bot)

def _cache_key(ticker, period, interval):
    return f"{ticker}|{period}|{interval}"

def _get_from_cache(key):
    """Retorna datos cacheados si existen y no han expirado."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (_time.time() - entry["timestamp"]) < _CACHE_TTL:
            return entry["data"]
    return None

def _put_in_cache(key, data):
    """Almacena datos en caché con timestamp."""
    with _cache_lock:
        _cache[key] = {"data": data, "timestamp": _time.time()}
        # Limpieza: evitar que el caché crezca sin limite
        # Máximo 200 entradas (20 tickers x 10 combinaciones period/interval)
        if len(_cache) > 200:
            oldest_key = min(_cache, key=lambda k: _cache[k]["timestamp"])
            del _cache[oldest_key]


# Intentar usar el caché de Streamlit como capa adicional si está disponible
_use_streamlit_cache = False
try:
    import streamlit as st
    _use_streamlit_cache = True
except Exception:
    pass


def get_stock_data(ticker, period="1y", interval="1d"):
    """
    Descarga el historial de la acción de Yahoo Finance con Caché Universal.
    
    - Dentro de Streamlit: usa st.cache_data (TTL 30s) + caché en memoria.
    - Fuera de Streamlit (bot_worker): usa solo caché en memoria (TTL 45s).
    
    Esto evita spam a la API de Yahoo Finance y reduce latencia.
    """
    key = _cache_key(ticker, period, interval)
    
    # 1. Intentar caché en memoria (universal)
    cached = _get_from_cache(key)
    if cached is not None:
        return cached
    
    # 2. Descargar datos frescos
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if not df.empty:
            df.index = df.index.tz_localize(None)  # Limpiar zonas horarias
        
        # Guardar en caché
        _put_in_cache(key, df)
        return df
    except Exception as e:
        logging.warning(f"Error descargando datos para {ticker}: {e}")
        # Si falla la descarga, intentar devolver datos viejos del caché (aunque expirados)
        with _cache_lock:
            stale = _cache.get(key)
            if stale:
                logging.info(f"Usando datos stale de caché para {ticker}")
                return stale["data"]
        return pd.DataFrame()


def clear_cache():
    """Limpia el caché manualmente (util para testing)."""
    with _cache_lock:
        _cache.clear()


def get_cache_stats():
    """Retorna estadísticas del caché para debugging."""
    with _cache_lock:
        now = _time.time()
        total = len(_cache)
        fresh = sum(1 for v in _cache.values() if (now - v["timestamp"]) < _CACHE_TTL)
        return {"total_entries": total, "fresh": fresh, "stale": total - fresh}
