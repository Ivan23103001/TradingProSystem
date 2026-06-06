"""
Inicialización lazy de módulos core del backend.

Extraído de backend/main.py para reducir su tamaño y mejorar
la testabilidad de la fase de arranque. La función principal
init_all_modules() carga los 7 módulos core y retorna un dict
con los resultados.

Uso desde main.py:
    from backend.init_modules import init_all_modules
    result = init_all_modules(_BASE_DIR)
    # Asignar globales desde result['modules']
"""

import os
import logging
import pathlib


def init_all_modules(base_dir: pathlib.Path) -> dict:
    """
    Inicializa TODOS los módulos core y retorna un dict con resultados.

    Args:
        base_dir: Ruta absoluta al directorio raíz del proyecto.

    Returns:
        {
            "ok": bool,
            "errors": list[str],
            "db_file": str,
            "modules": {
                "get_stock_data": callable | None,
                "get_cache_stats": callable | None,
                "apply_strategy": callable | None,
                "get_spy_sentiment": callable | None,
                "is_market_open": callable | None,
                "BrokerClient": type | None,
                "init_db": callable | None,
                "get_trade_history": callable | None,
                "calculate_ml_rolling_accuracy": callable | None,
                "TradingBrain": type | None,
            }
        }
    """
    # Re-leer DB_FILE desde el entorno (asegura consistencia en hilo hijo)
    db_file = os.environ.get("DB_FILE", str(base_dir / "trade_history.db"))
    logging.info(f"🔄 DB_FILE re-leído del entorno: {db_file}")

    errors = []
    modules = {}

    try:
        # ── data_fetcher ──
        try:
            from core.data_fetcher import get_stock_data as gsd, get_cache_stats as gcs
            modules["get_stock_data"] = gsd
            modules["get_cache_stats"] = gcs
            logging.info("✅ data_fetcher cargado.")
        except Exception as e:
            errors.append(f"data_fetcher: {e}")
            modules["get_stock_data"] = None
            modules["get_cache_stats"] = None
            logging.error(f"data_fetcher falló: {e}")

        # ── strategy ──
        try:
            from core.strategy import apply_strategy as ap, get_spy_sentiment as gss
            modules["apply_strategy"] = ap
            modules["get_spy_sentiment"] = gss
            logging.info("✅ strategy cargado.")
        except Exception as e:
            errors.append(f"strategy: {e}")
            modules["apply_strategy"] = None
            modules["get_spy_sentiment"] = None
            logging.error(f"strategy falló: {e}")

        # ── simulator ──
        try:
            from core.simulator import is_market_open as imo
            modules["is_market_open"] = imo
            logging.info("✅ simulator cargado.")
        except Exception as e:
            errors.append(f"simulator: {e}")
            modules["is_market_open"] = None
            logging.error(f"simulator falló: {e}")

        # ── broker ──
        try:
            from core.broker import BrokerClient as BC
            modules["BrokerClient"] = BC
            logging.info("✅ broker cargado.")
        except Exception as e:
            errors.append(f"broker: {e}")
            modules["BrokerClient"] = None
            logging.error(f"broker falló: {e}")

        # ── brain (DEBE ir ANTES que database para DB_FILE sincronizado) ──
        try:
            from core.brain import TradingBrain as TB, DB_FILE as BRAIN_DB_FILE
            modules["TradingBrain"] = TB
            if not os.environ.get("DB_FILE"):
                db_file = BRAIN_DB_FILE
                os.environ["DB_FILE"] = db_file
            logging.info(f"✅ brain importado (DB_FILE={BRAIN_DB_FILE}).")
            if modules["TradingBrain"]:
                modules["TradingBrain"].initialize()
                logging.info("✅ TradingBrain inicializado.")
        except Exception as e:
            errors.append(f"brain: {e}")
            modules["TradingBrain"] = None
            logging.error(f"brain falló: {e}")

        # ── database (con DB_FILE ya resuelto) ──
        try:
            from core.database import init_db as idb, get_trade_history as gth
            modules["init_db"] = idb
            modules["get_trade_history"] = gth
            if modules["init_db"]:
                logging.info(f"Inicializando base de datos... (DB_FILE={db_file})")
                modules["init_db"](db_file)
                if db_file and os.path.exists(db_file):
                    logging.info(f"✅ database inicializada — DB existe en {db_file}")
                else:
                    logging.warning(f"database inicializada pero DB_FILE={db_file} no encontrada en disco.")
            else:
                errors.append("database: init_db es None")
                logging.error("database: init_db es None tras import.")
        except Exception as e:
            errors.append(f"database: {e}")
            modules["init_db"] = None
            modules["get_trade_history"] = None
            logging.error(f"database falló: {e}")

        # ── ml_engine ──
        try:
            from core.ml_engine import calculate_ml_rolling_accuracy as cml
            modules["calculate_ml_rolling_accuracy"] = cml
            logging.info("✅ ml_engine cargado.")
        except Exception as e:
            errors.append(f"ml_engine: {e}")
            modules["calculate_ml_rolling_accuracy"] = None
            logging.error(f"ml_engine falló: {e}")

    except Exception as e:
        errors.append(f"CRITICAL_UNHANDLED: {e}")
        logging.critical(f"CRITICAL INIT ERROR: {e}")
        import traceback
        traceback.print_exc()

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "db_file": db_file,
        "modules": modules,
    }