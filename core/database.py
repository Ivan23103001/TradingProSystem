"""
Módulo centralizado de acceso a la base de datos SQLite.

Resuelve el problema de concurrencia entre app.py (Streamlit) y bot_worker.py
al usar WAL (Write-Ahead Logging) y un timeout generoso para conexiones.

Ambos procesos DEBEN usar este módulo en lugar de sqlite3.connect() directo.
"""

import sqlite3
import os
import logging
import pathlib

_BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
DB_NAME = str(_BASE_DIR / "trade_history.db")


def get_connection(db_path=None):
    """
    Abre una conexión SQLite configurada para concurrencia segura.
    
    - WAL mode: permite lecturas simultáneas con escrituras.
    - timeout=15: espera hasta 15s si otro proceso tiene el lock.
    - check_same_thread=False: permite compartir conexión entre threads.
    """
    path = db_path or DB_NAME
    conn = sqlite3.connect(path, timeout=15, check_same_thread=False)
    
    # Activar WAL (Write-Ahead Logging) — crucial para concurrencia
    conn.execute("PRAGMA journal_mode=WAL;")
    # Activar foreign keys por buenas prácticas
    conn.execute("PRAGMA foreign_keys=ON;")
    # Timeout de busy (redundante con el parámetro timeout, pero explícito)
    conn.execute("PRAGMA busy_timeout=15000;")
    
    return conn


def init_db(db_path=None):
    """Inicializa las tablas necesarias si no existen."""
    conn = get_connection(db_path)
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS trades
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      fecha TEXT, ticker TEXT, tipo TEXT,
                      precio REAL, cantidad REAL, score INTEGER,
                      pnl REAL DEFAULT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS equity_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      fecha TEXT, total_equity REAL)''')
        # Índices para consultas frecuentes
        c.execute('''CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_trades_fecha ON trades(fecha)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_equity_fecha ON equity_history(fecha)''')
        conn.commit()
    except Exception as e:
        logging.error(f"Error inicializando DB: {e}")
    finally:
        conn.close()


def save_trade(ticker, tipo, precio, cantidad, score, db_path=None):
    """Guarda un trade en la base de datos de forma segura."""
    from datetime import datetime
    conn = get_connection(db_path)
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO trades (fecha, ticker, tipo, precio, cantidad, score) VALUES (?,?,?,?,?,?)",
            (fecha, ticker, tipo, precio, cantidad, score)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        logging.error(f"DB locked al guardar trade {ticker}: {e}")
    except Exception as e:
        logging.error(f"Error guardando trade: {e}")
    finally:
        conn.close()


def save_equity(equity, db_path=None):
    """Guarda un snapshot de equity en la base de datos."""
    from datetime import datetime
    conn = get_connection(db_path)
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO equity_history (fecha, total_equity) VALUES (?,?)",
            (fecha, equity)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        logging.error(f"DB locked al guardar equity: {e}")
    except Exception as e:
        logging.error(f"Error guardando equity: {e}")
    finally:
        conn.close()


def get_trade_history(limit=500, db_path=None):
    """Obtiene el historial de trades más recientes."""
    import pandas as pd
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return pd.DataFrame()
    conn = get_connection(path)
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM trades ORDER BY id DESC LIMIT {limit}", conn
        )
        return df
    except Exception as e:
        logging.error(f"Error leyendo historial: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_equity_history(limit=1000, db_path=None):
    """Obtiene el historial de equity más reciente."""
    import pandas as pd
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return pd.DataFrame()
    conn = get_connection(path)
    try:
        df = pd.read_sql_query(
            f"SELECT * FROM equity_history ORDER BY id DESC LIMIT {limit}", conn
        )
        return df
    except Exception as e:
        logging.error(f"Error leyendo equity history: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def update_last_trade_pnl(ticker, exit_price, reason, db_path=None):
    """
    Busca la última operación abierta para un ticker en la base de datos (pnl IS NULL)
    y calcula y guarda el PnL real usando el precio de salida y el motivo.
    """
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return
        
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        # Buscar el último trade de este ticker que aún no tiene PnL calculado
        cursor.execute(
            "SELECT id, tipo, precio, cantidad FROM trades WHERE ticker = ? AND pnl IS NULL ORDER BY id DESC LIMIT 1",
            (ticker,)
        )
        row = cursor.fetchone()
        if row:
            trade_id, tipo, entry_price, qty_or_amt = row
            if entry_price > 0:
                pnl_pct = (exit_price - entry_price) / entry_price
                if "SHORT" in tipo or "sell" in tipo.lower():
                    pnl_pct = -pnl_pct
                    
                pnl_cash = pnl_pct * qty_or_amt
                
                cursor.execute(
                    "UPDATE trades SET pnl = ? WHERE id = ?",
                    (pnl_cash, trade_id)
                )
                conn.commit()
                logging.info(f"💾 [DB Risk] PnL Actualizado para {ticker}: ${pnl_cash:.2f} ({pnl_pct*100:.1f}%) | Motivo: {reason}")
        else:
            logging.debug(f"No se encontró trade abierto sin PnL para {ticker} en la DB.")
    except Exception as e:
        logging.error(f"Error actualizando PnL para {ticker}: {e}")
    finally:
        conn.close()

def archive_old_trades(days_to_keep=90, db_path=None):
    """
    Borra trades y registros de equity más antiguos que 'days_to_keep'
    para evitar que la base de datos crezca infinitamente.
    """
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return
        
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        
        # Calcular fecha límite
        cursor.execute(f"SELECT date('now', '-{days_to_keep} days')")
        cutoff_date = cursor.fetchone()[0]
        
        # Borrar trades viejos
        cursor.execute("DELETE FROM trades WHERE fecha < ?", (cutoff_date,))
        deleted_trades = cursor.rowcount
        
        # Borrar equity_history viejo
        cursor.execute("DELETE FROM equity_history WHERE fecha < ?", (cutoff_date,))
        deleted_equity = cursor.rowcount
        
        # Optimizar base de datos
        cursor.execute("VACUUM")
        conn.commit()
        
        if deleted_trades > 0 or deleted_equity > 0:
            logging.info(f"🧹 [DB Mantenimiento] Eliminados {deleted_trades} trades y {deleted_equity} registros de equity anteriores a {cutoff_date}.")
    except Exception as e:
        logging.error(f"Error durante el mantenimiento de la base de datos: {e}")
    finally:
        conn.close()
