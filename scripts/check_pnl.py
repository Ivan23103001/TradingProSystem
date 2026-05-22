import sqlite3
import yfinance as yf
from datetime import datetime

def check_pnl():
    conn = sqlite3.connect('trade_history.db')
    cursor = conn.cursor()
    # Get today's date dynamically
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT ticker, tipo, precio, cantidad FROM trades WHERE fecha LIKE ?", (f"{today}%",))
    rows = cursor.fetchall()
    
    if not rows:
        print("No se encontraron transacciones registradas hoy.")
        # Let's look at recent ones in general to be sure
        cursor.execute("SELECT ticker, tipo, precio, cantidad, fecha FROM trades ORDER BY id DESC LIMIT 5")
        rows = cursor.fetchall()
        if rows:
            print("\nÚltimas 5 transacciones registradas:")
            for r in rows:
                print(f"Ticker: {r[0]}, Tipo: {r[1]}, Precio Entrada: ${r[2]:.2f}, Cant/Amt: {r[3]}, Fecha: {r[4]}")
        return

    print(f"--- Análisis de Ganancias del Día ({today}) ---")
    total_unrealized = 0.0
    for ticker, tipo, entry_price, qty_or_amt in rows:
        # Get current price
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            
            # Note: in config, sizing_mode was QTY but trade_amount was 1.0 (qty)
            # but sometimes it can be Notional
            # The bot_worker logs as QTY if configuration says QTY
            # Let's assume QTY based on config.
            
            pnl = 0.0
            if "LONG" in tipo:
                pnl = (current_price - entry_price) * qty_or_amt
                dir_str = "Long (Compra)"
            elif "SHORT" in tipo:
                pnl = (entry_price - current_price) * qty_or_amt
                dir_str = "Short (Venta Corto)"
            else:
                pnl = 0.0
                dir_str = "Desconocido"
            
            total_unrealized += pnl
            status_pnl = "GANANCIA" if pnl > 0 else "PÉRDIDA"
            print(f"[{dir_str}] {ticker}: Entrada ${entry_price:.2f} | Actual ${current_price:.2f} | {status_pnl}: ${pnl:.2f}")
        except Exception as e:
            print(f"Error procesando {ticker}: {e}")
            
    print(f"\nRESULTADO TOTAL TEÓRICO: {'+' if total_unrealized > 0 else ''}${total_unrealized:.2f}")
    conn.close()

if __name__ == "__main__":
    check_pnl()
