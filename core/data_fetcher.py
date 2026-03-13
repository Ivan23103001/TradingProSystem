import yfinance as yf
import pandas as pd
import streamlit as st

@st.cache_data(ttl=30) # Caché de 30 segundos
def get_stock_data(ticker, period="1y", interval="1d"):
    """
    Descarga el historial de la acción de Yahoo Finance optimizado con Caché.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period, interval=interval)
        if not df.empty:
            df.index = df.index.tz_localize(None) # Limpiar zonas horarias
        return df
    except Exception as e:
        print(f"Error descargando datos para {ticker}: {e}")
        return pd.DataFrame()
