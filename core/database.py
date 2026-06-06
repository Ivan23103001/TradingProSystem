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
import threading

_BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
DB_NAME = str(_BASE_DIR / "trade_history.db")

# Pool de conexiones thread-local: cada hilo reutiliza su propia conexión.
# SQLite en modo WAL + check_same_thread=False permite compartir la conexión
# entre hilos, pero thread-local evita contención de cursor.
_tls = threading.local()


def _new_connection(db_path):
    """Crea una nueva conexión SQLite configurada para concurrencia segura."""
    conn = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def get_connection(db_path=None):
    """
    Obtiene una conexión SQLite persistente por hilo (thread-local pool).
    
    - WAL mode: permite lecturas simultáneas con escrituras.
    - timeout=15: espera hasta 15s si otro proceso tiene el lock.
    - check_same_thread=False: permite compartir conexión entre threads.
    - Reutiliza la conexión del hilo en llamadas sucesivas (sin abrir/cerrar por query).
    """
    path = db_path or DB_NAME
    pool = getattr(_tls, 'conn_pool', None)
    if pool is None:
        pool = {}
        _tls.conn_pool = pool
    if path not in pool:
        pool[path] = _new_connection(path)
    return pool[path]


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
        c.execute('''CREATE TABLE IF NOT EXISTS bot_state
                     (id INTEGER PRIMARY KEY CHECK (id = 1),
                      state_json TEXT NOT NULL,
                      updated_at TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS audit_log
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp TEXT NOT NULL,
                      event_type TEXT NOT NULL,
                      ip_address TEXT,
                      user_agent TEXT,
                      details_json TEXT,
                      severity TEXT DEFAULT 'INFO')''')
        # Índices para consultas frecuentes
        c.execute('''CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_trades_fecha ON trades(fecha)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_equity_fecha ON equity_history(fecha)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type)''')
        conn.commit()
        logging.info("✅ Base de datos inicializada: tablas trades, equity_history, bot_state y audit_log listas.")
    except Exception as e:
        logging.error(f"Error inicializando DB: {e}")
        # Si falla la inicialización, remover la conexión dañada del pool
        path = db_path or DB_NAME
        pool = getattr(_tls, 'conn_pool', None)
        if pool and path in pool:
            try:
                pool[path].close()
            except Exception:
                pass
            del pool[path]


from typing import Optional, Dict, Any

def save_trade(ticker: str, tipo: str, precio: float, cantidad: float, score: int, db_path: Optional[str] = None) -> None:
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


def save_equity(equity: float, db_path: Optional[str] = None) -> None:
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


def get_trade_history(limit: int = 500, db_path: Optional[str] = None) -> 'pd.DataFrame':
    """Obtiene el historial de trades más recientes."""
    import pandas as pd
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return pd.DataFrame()
    conn = get_connection(path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", conn, params=(limit,)
        )
        return df
    except Exception as e:
        logging.error(f"Error leyendo historial: {e}")
        return pd.DataFrame()


def get_equity_history(limit: int = 1000, db_path: Optional[str] = None) -> 'pd.DataFrame':
    """Obtiene el historial de equity más reciente."""
    import pandas as pd
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return pd.DataFrame()
    conn = get_connection(path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM equity_history ORDER BY id DESC LIMIT ?", conn, params=(limit,)
        )
        return df
    except Exception as e:
        logging.error(f"Error leyendo equity history: {e}")
        return pd.DataFrame()


def update_last_trade_pnl(ticker: str, exit_price: float, reason: str, db_path: Optional[str] = None) -> None:
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
            trade_id, tipo, entry_price, notional_or_qty = row
            if entry_price > 0:
                if "SHORT" in tipo or "sell" in tipo.lower():
                    # Para SHORT: notional_or_qty guarda el notional (USD invertido).
                    # shares = notional / entry_price
                    # PnL = (entry_price - exit_price) * shares
                    shares = notional_or_qty / entry_price
                    pnl_cash = (entry_price - exit_price) * shares
                else:
                    # Para LONG: notional_or_qty guarda el notional (USD invertido).
                    # shares = notional / entry_price
                    # PnL = (exit_price - entry_price) * shares
                    shares = notional_or_qty / entry_price
                    pnl_cash = (exit_price - entry_price) * shares
                
                cursor.execute(
                    "UPDATE trades SET pnl = ? WHERE id = ?",
                    (pnl_cash, trade_id)
                )
                conn.commit()
                pnl_pct = (pnl_cash / notional_or_qty) * 100
                logging.info(f"💾 [DB Risk] PnL Actualizado para {ticker}: ${pnl_cash:.2f} ({pnl_pct:.1f}%) | Motivo: {reason}")
        else:
            logging.debug(f"No se encontró trade abierto sin PnL para {ticker} en la DB.")
    except Exception as e:
        logging.error(f"Error actualizando PnL para {ticker}: {e}")

def save_bot_state(state_dict, db_path=None):
    """
    Persiste el estado volátil del bot (state_memory) como JSON en la tabla bot_state.
    Usa INSERT OR REPLACE para mantener una sola fila (id=1).
    """
    import json
    from datetime import datetime
    path = db_path or DB_NAME
    conn = get_connection(path)
    try:
        state_json = json.dumps(state_dict, default=str, ensure_ascii=False)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT OR REPLACE INTO bot_state (id, state_json, updated_at) VALUES (1, ?, ?)",
            (state_json, now_str)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Error guardando bot_state: {e}")


def load_bot_state(db_path=None):
    """
    Carga el último estado persistido del bot desde la tabla bot_state.
    Retorna un dict o {} si no hay estado guardado.
    """
    import json
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return {}
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT state_json FROM bot_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return {}
    except Exception as e:
        logging.error(f"Error cargando bot_state: {e}")
        return {}


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
        cursor.execute("SELECT date('now', ?)", (f'-{days_to_keep} days',))
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


def save_audit_log(event_type, details=None, ip_address=None, user_agent=None, severity="INFO", db_path=None):
    """
    Registra un evento de auditoría en la tabla audit_log.

    Args:
        event_type: Tipo de evento (ej. 'CONFIG_CHANGE', 'LOGIN', 'TRADE_EXECUTED', 'CIRCUIT_BREAKER')
        details: Dict o string con información adicional del evento
        ip_address: IP del cliente que originó el evento
        user_agent: User-Agent del cliente
        severity: Nivel de severidad ('INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    import json
    from datetime import datetime

    path = db_path or DB_NAME
    conn = get_connection(path)
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details_json = json.dumps(details, default=str, ensure_ascii=False) if details else None
        conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, ip_address, user_agent, details_json, severity) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, event_type, ip_address, user_agent, details_json, severity)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Error guardando audit_log [{event_type}]: {e}")


def get_audit_logs(limit=100, event_type=None, db_path=None):
    """
    Obtiene los registros de auditoría más recientes.
    Opcionalmente filtra por event_type.
    """
    import pandas as pd
    path = db_path or DB_NAME
    if not os.path.exists(path):
        return pd.DataFrame()
    conn = get_connection(path)
    try:
        if event_type:
            df = pd.read_sql_query(
                "SELECT * FROM audit_log WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                conn, params=(event_type, limit)
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", conn, params=(limit,)
            )
        return df
    except Exception as e:
        logging.error(f"Error leyendo audit_log: {e}")
        return pd.DataFrame()
