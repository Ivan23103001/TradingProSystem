"""
Servidor HTTP mínimo que el bot_worker levanta en segundo plano.
GET http://localhost:8001/health → {"status": "ok", "uptime_s": 3600}
"""
from fastapi import FastAPI
from datetime import datetime
import threading
import uvicorn
import time

app = FastAPI()
_start_time = time.time()
_state = {"last_scan": None, "total_trades_session": 0, "last_error": None, "is_retraining": False}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - _start_time),
        "last_scan": _state.get("last_scan"),
        "trades_session": _state.get("total_trades_session"),
        "last_error": _state.get("last_error"),
        "is_retraining": _state.get("is_retraining", False)
    }

@app.get("/retrain-status")
def retrain_status():
    """Estado del hilo de reentrenamiento ML en background."""
    return {"is_retraining": _state.get("is_retraining", False)}

def start_health_server(port=8001):
    """Inicia el servidor en un thread daemon (no bloquea el worker)."""
    def _run():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
    t = threading.Thread(target=_run, daemon=True)
    t.start()
