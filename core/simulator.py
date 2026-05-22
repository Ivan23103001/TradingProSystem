import pandas as pd
import numpy as np
from datetime import datetime
import pytz

def is_market_open():
    try:
        et = pytz.timezone('US/Eastern')
        now = datetime.now(et)
        if now.weekday() >= 5: return False, "Mercado cerrado (Fin de semana)"
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        if now < market_open: return False, f"Mercado abre a las {market_open.strftime('%I:%M %p')}"
        elif now > market_close: return False, "Mercado cerrado"
        else: return True, "Mercado ABIERTO"
    except: return True, "Habilitado"

def check_critical_hours(dt_now):
    try:
        start_safe = dt_now.replace(hour=9, minute=45, second=0, microsecond=0)
        end_safe = dt_now.replace(hour=15, minute=45, second=0, microsecond=0)
        
        # Filtro de apertura y cierre
        if dt_now < start_safe or dt_now > end_safe: 
            return False, "Fase Crítica (Apertura/Cierre)"
            
        # Filtro de Almuerzo ("Lunch Chop") donde el volumen institucional cae y el precio se vuelve ruidoso
        lunch_start = dt_now.replace(hour=12, minute=0, second=0, microsecond=0)
        lunch_end = dt_now.replace(hour=13, minute=30, second=0, microsecond=0)
        if lunch_start <= dt_now <= lunch_end:
            return False, "Fase Crítica (Rango de Almuerzo / Efecto Choppy)"
            
        return True, "Horario Seguro"
    except: return True, "Horario habilitado"

def run_simulation(df, initial_capital=100000.0, position_sizing=1.0, 
                   stop_loss=0.05, take_profit=0.15,
                   use_trailing_stop=True, use_atr_stop=True,
                   confirmation_bars=2, cooldown_days=5,
                   slippage_pct=0.0005, commission_fixed=0.0):
    
    if df.empty or 'Signal' not in df.columns:
        return {'history': pd.DataFrame(), 'metrics': {
            'total_trades': 0, 'trades_won': 0, 'trades_lost': 0, 'win_rate': 0.0, 'max_drawdown': 0.0,
            'net_return': 0.0, 'final_value': initial_capital, 'sharpe_ratio': 0.0, 'sortino_ratio': 0.0
        }}
        
    capital = float(initial_capital)
    position = 0.0
    entry_price = 0.0
    highest_since_entry = 0.0
    lowest_since_entry = 999999.0
    trailing_stop_price = 0.0
    cooldown_counter = 0
    consecutive_buy_signals = 0
    consecutive_sell_signals = 0
    history = []
    trades_won, trades_lost = 0, 0
    peak_capital = float(initial_capital)
    max_drawdown = 0.0
    pnl_per_trade = []
    
    # Kelly adaptativo desde data.attrs si existe
    kelly_sizing = df.attrs.get('kelly_size', position_sizing)
    
    for idx_pos, (index, row) in enumerate(df.iterrows()):
        price = float(row['Close'])
        signal = float(row['Signal'])
        accion_tomada = "-"
        if price <= 0: continue
        if cooldown_counter > 0: cooldown_counter -= 1
        
        if signal >= 0.7: consecutive_buy_signals += 1; consecutive_sell_signals = 0
        elif signal <= -0.7: consecutive_sell_signals += 1; consecutive_buy_signals = 0
        else: consecutive_buy_signals = 0; consecutive_sell_signals = 0
        
        # SL dinámico por ATR
        dynamic_sl = stop_loss
        if use_atr_stop and 'ATR' in df.columns:
            atr_val = _safe(row['ATR'])
            if atr_val > 0 and price > 0:
                dynamic_sl = max(0.02, min(0.15, (2.0 * atr_val) / price))
        
        # EXIT LOGIC
        if position != 0:
            if position > 0:
                highest_since_entry = max(highest_since_entry, price)
                ganancia_pct = (price - entry_price) / entry_price
                if use_trailing_stop:
                    gain = (highest_since_entry - entry_price) / entry_price
                    if gain >= 0.10: trailing_stop_price = entry_price * 1.05
                    elif gain >= 0.05: trailing_stop_price = entry_price
            else:
                lowest_since_entry = min(lowest_since_entry, price)
                ganancia_pct = (entry_price - price) / entry_price
                if use_trailing_stop:
                    gain = (entry_price - lowest_since_entry) / entry_price
                    if gain >= 0.10: trailing_stop_price = entry_price * 0.95
                    elif gain >= 0.05: trailing_stop_price = entry_price
            
            cierre = False
            razon = ""
            if use_trailing_stop and trailing_stop_price > 0:
                if (position > 0 and price <= trailing_stop_price) or (position < 0 and price >= trailing_stop_price):
                    cierre, razon = True, "TRAILING STOP"
            if not cierre and ganancia_pct <= -dynamic_sl:
                cierre, razon = True, f"STOP LOSS ({dynamic_sl*100:.1f}%)"
            if not cierre and ganancia_pct >= take_profit:
                cierre, razon = True, "TAKE PROFIT"
            if not cierre and ((position > 0 and signal <= -0.5) or (position < 0 and signal >= 0.5)):
                cierre, razon = True, "SEÑAL CONTRARIA"
                
            if cierre:
                accion_tomada = razon
                if position > 0:
                    capital += position * (price * (1 - slippage_pct)) - commission_fixed
                    if price * (1 - slippage_pct) > entry_price: trades_won += 1
                    else: trades_lost += 1
                    pnl_per_trade.append((price * (1 - slippage_pct)) - entry_price)
                else:
                    exit_p_short = price * (1 + slippage_pct)
                    pnl_cash = (entry_price - exit_p_short) * abs(position)
                    capital += (abs(position) * entry_price) + pnl_cash - commission_fixed
                    if exit_p_short < entry_price: trades_won += 1
                    else: trades_lost += 1
                    pnl_per_trade.append(entry_price - exit_p_short)
                if "STOP LOSS" in razon: cooldown_counter = cooldown_days
                position, entry_price, trailing_stop_price = 0.0, 0.0, 0.0
                highest_since_entry, lowest_since_entry = 0.0, 999999.0

        # ENTRY LOGIC
        if position == 0 and accion_tomada == "-":
            if cooldown_counter > 0:
                accion_tomada = f"COOLDOWN ({cooldown_counter}d)"
            else:
                # Usar Kelly o position_sizing inicial
                cap_to_inv = capital * kelly_sizing
                if cap_to_inv > capital: cap_to_inv = capital
                
                if signal >= 0.7 and consecutive_buy_signals >= confirmation_bars:
                    entry_p = price * (1 + slippage_pct)
                    position = (cap_to_inv - commission_fixed) / entry_p
                    capital -= cap_to_inv
                    entry_price = entry_p
                    highest_since_entry = entry_p
                    accion_tomada = f"COMPRA (LONG)"
                    consecutive_buy_signals = 0
                elif signal <= -0.7 and consecutive_sell_signals >= confirmation_bars:
                    entry_p = price * (1 - slippage_pct)
                    position = -((cap_to_inv - commission_fixed) / entry_p)
                    capital -= cap_to_inv
                    entry_price = entry_p
                    lowest_since_entry = entry_p
                    accion_tomada = f"VENTA (SHORT)"
                    consecutive_sell_signals = 0

        # VALOR
        if position >= 0: val_port = capital + (position * price)
        else: val_port = capital + (abs(position) * entry_price) + (entry_price - price) * abs(position)
        
        peak_capital = max(peak_capital, val_port)
        max_drawdown = max(max_drawdown, ((peak_capital - val_port) / peak_capital) * 100)
        
        history.append({
            'Fecha': index, 'Accion': accion_tomada, 'Precio': round(price, 4), 'Valor_Total': round(val_port, 2),
            'Kelly_Used': round(kelly_sizing, 4)
        })
        
    hist_df = pd.DataFrame(history)
    val_final = hist_df['Valor_Total'].iloc[-1] if not hist_df.empty else initial_capital
    retorno = ((val_final - initial_capital) / initial_capital) * 100
    
    return {'history': hist_df, 'metrics': {
        'total_trades': trades_won + trades_lost, 'win_rate': round(trades_won/((trades_won+trades_lost)+1e-9)*100, 1),
        'net_return': round(retorno, 2), 'max_drawdown': round(max_drawdown, 2), 'final_value': round(val_final, 2)
    }}

def _safe(val, default=0.0):
    try: return float(val) if pd.notna(val) else default
    except: return default

def run_monte_carlo(metrics, num_simulations=1000, horizon=20):
    results = []
    wr = metrics['win_rate'] / 100
    avg_r = metrics['net_return'] / (metrics['total_trades'] + 1e-9)
    for _ in range(num_simulations):
        current = 1.0
        for _ in range(horizon):
            outcome = 1 if np.random.random() < wr else -1
            current *= (1 + (outcome * avg_r/100) * (1 + (np.random.random() - 0.5) * 0.2))
        results.append(current)
    return np.array(results)
