import os
import sys
import pandas as pd
from core.data_fetcher import get_stock_data
from core.strategy import apply_strategy
from core.ml_engine import train_trading_model

def auto_train():
    print("==================================================")
    print(" [AI] INICIANDO ENTRENAMIENTO DEL ENSAMBLE RF+GB ")
    print("==================================================")
    
    # 1. Definir el Universo de Entrenamiento (puedes cambiarlo)
    # Se recomienda mezclar acciones tech (volátiles) y bancos (estables) 
    # para que la IA entienda múltiples regímenes de mercado.
    tickers = ["AAPL", "NVDA", "TSLA", "MSFT", "JPM", "V"]
    
    # Periodo: 2 años atrás es un buen balance para evitar "olvidos" pero estar al día
    period = "2y"
    interval = "1d"
    
    print(f"Descargando {period} de datos históricos para: {', '.join(tickers)}")
    
    all_data = []
    for ticker in tickers:
        print(f" -> Obteniendo y analizando {ticker}...")
        try:
            df = get_stock_data(ticker, period=period, interval=interval)
            if df is not None and not df.empty:
                df_strategy = apply_strategy(df, ticker_symbol=ticker)
                if df_strategy is not None and not df_strategy.empty:
                    all_data.append(df_strategy)
        except Exception as e:
            print(f" [!] Error descargando/procesando {ticker}: {e}")
            
    if not all_data:
        print("[ERROR] No se pudieron descargar datos para entrenar.")
        sys.exit(1)
        
    # Combinar todos los históricos en un super-dataset
    super_df = pd.concat(all_data, axis=0)
    super_df = super_df.sort_index()
    print(f"\n[SUCCESS] Dataset creado con {len(super_df)} velas diarias combinadas.")
    
    # 2. Entrenar los Modelos
    print("\n[AI] Entrenando Ensamble Híbrido (Random Forest + Gradient Boosting)...")
    print("[WAIT] Esto puede tomar unos minutos dependiendo de tu CPU...")
    
    # Ajustamos max_depth y n_estimators para un cerebro denso
    accuracy, msg = train_trading_model(super_df, n_estimators=200, max_depth=15)
    
    if accuracy is not None:
        print("\n==================================================")
        print(" [SUCCESS] ENTRENAMIENTO COMPLETADO CON EXITO ")
        print("==================================================")
        print(f"[*] Precision Base en Test: {accuracy}")
        print("[-] Modelo guardado como: ml_trading_model.pkl (Actualizado)")
        print("\nEl bot principal usará automáticamente este nuevo cerebro en su próxima ejecución.")
    else:
        print(f"\n[ERROR] Fallo el entrenamiento: {msg}")

if __name__ == "__main__":
    auto_train()
