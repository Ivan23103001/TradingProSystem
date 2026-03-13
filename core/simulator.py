import pandas as pd
import numpy as np

def run_simulation(df, initial_capital=100000.0, position_sizing=1.0, stop_loss=0.05, take_profit=0.15):
    """
    Simulador Avanzado con Métricas de Rendimiento.
    Calcula Ganancias, Win Rate (Eficiencia) y Max Drawdown (Riesgo).
    """
    if df.empty or 'Signal' not in df.columns:
        return {'history': pd.DataFrame(), 'metrics': {}}
        
    capital = initial_capital
    position = 0 
    
    history = []
    trades_won = 0
    trades_lost = 0
    peak_capital = initial_capital
    max_drawdown = 0.0
    buy_price = 0.0
    
    # Check if the dataset has at least 50 length? Handled in strategy.py
    for index, row in df.iterrows():
        price = row['Close']
        signal = row['Signal']
        accion_tomada = "-"
        
        # ALGORITMO DE EJECUCIÓN (Manejo de Riesgo: Stop Loss / Take Profit)
        if position > 0:
            ganancia_pct = (price - buy_price) / buy_price
            if ganancia_pct <= -stop_loss:
                # Vender TODO por Stop Loss
                ganancia = position * price
                capital += ganancia
                trades_lost += 1
                position = 0
                accion_tomada = "STOP LOSS"
            elif ganancia_pct >= take_profit:
                # Vender TODO por Take Profit
                ganancia = position * price
                capital += ganancia
                trades_won += 1
                position = 0
                accion_tomada = "TAKE PROFIT"
                
        if accion_tomada == "-":
            # COMPRA
            capital_a_invertir = initial_capital * position_sizing
            if capital_a_invertir > capital:
                capital_a_invertir = capital
                
            if signal == 1 and capital_a_invertir >= price: 
                acciones = int(capital_a_invertir // price)
                costo = acciones * price
                
                # Actualizar precio de compra promedio (simplificado)
                buy_price = price if position == 0 else ((buy_price * position) + costo) / (position + acciones)
                
                capital -= costo
                position += acciones
                accion_tomada = "COMPRA"
                
            # VENTA
            elif signal <= -0.5 and position > 0:
                portion_to_sell = 1.0 if signal <= -1.0 else 0.5
                acciones_a_vender = int(position * portion_to_sell)
                if acciones_a_vender == 0 and position > 0:
                    acciones_a_vender = position
                    
                ganancia = acciones_a_vender * price
                capital += ganancia
                
                if price > buy_price:
                    trades_won += 1
                else:
                    trades_lost += 1
                    
                position -= acciones_a_vender
                accion_tomada = f"VENTA ({int(portion_to_sell*100)}%)"
            
        # MÉTRICAS DE RIESGO
        valor_portafolio = capital + (position * price)
        
        if valor_portafolio > peak_capital:
            peak_capital = valor_portafolio
            
        drawdown = ((peak_capital - valor_portafolio) / peak_capital) * 100
        if drawdown > max_drawdown:
            max_drawdown = drawdown
        
        history.append({
            'Fecha': index, 
            'Acion_Realizada': accion_tomada, 
            'Precio_Ejecucion': price,
            'Capital_Efectivo': capital, 
            'Acciones_Poseidas': position, 
            'Valor_Total': valor_portafolio
        })
        
    hist_df = pd.DataFrame(history)
    
    # CALCULAR MÉTRICAS FINALES
    total_trades = trades_won + trades_lost
    win_rate = (trades_won / total_trades * 100) if total_trades > 0 else 0.0
    
    valor_final = capital + (position * df['Close'].iloc[-1])
    retorno_neto = ((valor_final - initial_capital) / initial_capital) * 100
    
    # Calcular Rendimiento Diario y ratios
    hist_df['Rendimiento_Diario'] = hist_df['Valor_Total'].pct_change()
    mean_rend = hist_df['Rendimiento_Diario'].mean()
    std_rend = hist_df['Rendimiento_Diario'].std()
    
    # Anualizar (252 días de trading por año)
    sharpe_ratio = (mean_rend / std_rend) * np.sqrt(252) if std_rend > 0 else 0.0
    
    downside_rend = hist_df[hist_df['Rendimiento_Diario'] < 0]['Rendimiento_Diario']
    downside_std = downside_rend.std()
    sortino_ratio = (mean_rend / downside_std) * np.sqrt(252) if downside_std > 0 else sharpe_ratio
    
    metrics = {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'net_return': retorno_neto,
        'final_value': valor_final,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio
    }
    
    return {'history': hist_df, 'metrics': metrics}
