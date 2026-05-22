"""Utilidad para verificar el estado de la base de datos."""

from core.database import get_trade_history, get_equity_history, get_connection
import os

DB_NAME = "trade_history.db"

def check_db():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found.")
        return
    
    print("Recent Trades:")
    trades = get_trade_history(limit=5)
    print(trades)
    
    print("\nEquity History (last 5):")
    equity = get_equity_history(limit=5)
    print(equity)
    
    # Verificar modo WAL
    conn = get_connection()
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    conn.close()
    print(f"\nJournal Mode: {mode}")

if __name__ == "__main__":
    check_db()
