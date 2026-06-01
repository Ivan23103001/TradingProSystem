import sys
import os
import pathlib
import asyncio
import concurrent.futures
import logging
import requests
import time
import threading
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure base directory is in python path
_BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
sys.path.append(str(_BASE_DIR))

# Cargar variables de entorno antes de cualquier import local
load_dotenv()

# ── Lazy placeholders (imports postponed to background thread) ──
# Uvicorn MUST bind to port 8000 immediately — ALL heavy init happens in lifespan.
get_stock_data, get_cache_stats = None, None
apply_strategy, get_spy_sentiment = None, None
is_market_open = None
BrokerClient = None
init_db, get_trade_history = None, None
calculate_ml_rolling_accuracy = None
TradingBrain, DB_FILE = None, None
_init_ok = False
_init_errors = []
_init_done = threading.Event()  # Señal de que la inicialización terminó

print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Uvicorn bindeando puerto 8000 — inicialización en background...")


def _init_all_modules():
    """Inicializa TODOS los módulos core en background (sin bloquear el bind de Uvicorn).
    Ultra-resiliente: incluso un crash total de imports no congela el backend."""
    global get_stock_data, get_cache_stats
    global apply_strategy, get_spy_sentiment, is_market_open
    global BrokerClient, init_db, get_trade_history
    global calculate_ml_rolling_accuracy, TradingBrain, DB_FILE
    global _init_ok, _init_errors

    errors = []

    try:
        # ── data_fetcher ──
        try:
            from core.data_fetcher import get_stock_data as gsd, get_cache_stats as gcs
            get_stock_data, get_cache_stats = gsd, gcs
            print(f"[INIT] ✅ data_fetcher cargado.")
        except Exception as e:
            errors.append(f"data_fetcher: {e}")
            print(f"[INIT] ❌ data_fetcher falló: {e}")

        # ── strategy ──
        try:
            from core.strategy import apply_strategy as ap, get_spy_sentiment as gss
            apply_strategy, get_spy_sentiment = ap, gss
            print(f"[INIT] ✅ strategy cargado.")
        except Exception as e:
            errors.append(f"strategy: {e}")
            print(f"[INIT] ❌ strategy falló: {e}")

        # ── simulator ──
        try:
            from core.simulator import is_market_open as imo
            is_market_open = imo
            print(f"[INIT] ✅ simulator cargado.")
        except Exception as e:
            errors.append(f"simulator: {e}")
            print(f"[INIT] ❌ simulator falló: {e}")

        # ── broker ──
        try:
            from core.broker import BrokerClient as BC
            BrokerClient = BC
            print(f"[INIT] ✅ broker cargado.")
        except Exception as e:
            errors.append(f"broker: {e}")
            print(f"[INIT] ❌ broker falló: {e}")

        # ── database ──
        try:
            from core.database import init_db as idb, get_trade_history as gth
            init_db, get_trade_history = idb, gth
            if init_db:
                print(f"[INIT] Inicializando base de datos... (DB_FILE={DB_FILE})")
                init_db()
                # Verificar que la DB se creó
                if DB_FILE and os.path.exists(DB_FILE):
                    print(f"[INIT] ✅ database inicializada — DB existe en {DB_FILE}")
                else:
                    print(f"[INIT] ⚠️ database inicializada pero DB_FILE={DB_FILE} no encontrada en disco.")
            else:
                errors.append("database: init_db es None")
                print(f"[INIT] ❌ database: init_db es None tras import.")
        except Exception as e:
            errors.append(f"database: {e}")
            print(f"[INIT] ❌ database falló: {e}")

        # ── ml_engine ──
        try:
            from core.ml_engine import calculate_ml_rolling_accuracy as cml
            calculate_ml_rolling_accuracy = cml
            print(f"[INIT] ✅ ml_engine cargado.")
        except Exception as e:
            errors.append(f"ml_engine: {e}")
            print(f"[INIT] ❌ ml_engine falló: {e}")

        # ── brain ──
        try:
            from core.brain import TradingBrain as TB, DB_FILE as DF
            TradingBrain, DB_FILE = TB, DF
            print(f"[INIT] ✅ brain importado (DB_FILE={DB_FILE}).")
            if TradingBrain:
                TradingBrain.initialize()
                print(f"[INIT] ✅ TradingBrain inicializado.")
        except Exception as e:
            errors.append(f"brain: {e}")
            print(f"[INIT] ❌ brain falló: {e}")

    except Exception as e:
        # Catch-all: NUNCA dejar que el hilo muera en silencio
        errors.append(f"CRITICAL_UNHANDLED: {e}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔥🔥🔥 CRITICAL INIT ERROR: {e}")
        import traceback
        traceback.print_exc()

    # ── SIEMPRE marcamos como terminado (aunque haya errores) ──
    if errors:
        _init_ok = False
        _init_errors = errors
        msg = " | ".join(errors)
        logging.error(f"Errores durante inicialización: {msg}")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️  Inicialización parcial — {len(errors)} módulo(s) con error. Uvicorn sigue activo.")
    else:
        _init_ok = True
        _init_errors = []
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Backend inicializado correctamente — {7} módulos cargados.")

    _init_done.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global executor
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=30)
    logging.info("ThreadPoolExecutor iniciado (30 workers).")

    # Lanzar inicialización en background thread — NO bloquea el bind de Uvicorn
    threading.Thread(target=_init_all_modules, name="backend-init", daemon=True).start()

    yield
    logging.info("Shutting down ThreadPoolExecutor...")
    executor.shutdown(wait=True)
    logging.info("ThreadPoolExecutor finalizado limpiamente.")

app = FastAPI(title="TradingProSystem API v5.0", lifespan=lifespan)

# --- API Key Auth Middleware (3.5) ---
# Lee API_KEY desde bot_config.json; si no existe, genera una por defecto
def _load_api_key():
    try:
        if TradingBrain is not None:
            config = TradingBrain.get_runtime_config()
            key = config.get("api_key", "")
            if key and len(key) >= 8:
                return key
    except Exception:
        pass
    # Generar clave por defecto si no existe en config
    default_key = os.getenv("TRADING_API_KEY", "tradingpro-api-key-change-me")
    return default_key

API_KEY = _load_api_key()

@app.middleware("http")
async def api_key_auth_middleware(request: Request, call_next):
    # Solo proteger endpoints POST /api/config y rutas sensibles
    if request.url.path in ("/api/config",) and request.method == "POST":
        auth_header = request.headers.get("X-API-Key", "")
        if not auth_header or auth_header != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "API Key inválida o ausente. Usa header X-API-Key."}
            )
    return await call_next(request)

from fastapi.responses import JSONResponse

# --- Rate Limiter para yfinance (2.3) ---
# Semáforo global: máximo 5 requests simultáneos a yfinance, con delay entre lotes
_yf_semaphore = threading.Semaphore(5)
_yf_last_call = 0.0
_YF_MIN_INTERVAL = 0.3  # 300ms mínimo entre requests para no triggerear rate-limit

def _rate_limited_fetch(ticker, period, interval, spy_sentiment):
    """Wrapper con rate-limit para llamadas a yfinance desde el pool."""
    global _yf_last_call
    with _yf_semaphore:
        elapsed = time.time() - _yf_last_call
        if elapsed < _YF_MIN_INTERVAL:
            time.sleep(_YF_MIN_INTERVAL - elapsed)
        _yf_last_call = time.time()
        return _analyze_ticker_sync(ticker, period, interval, spy_sentiment)

# Enable CORS for frontend ports and production domains
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    # Default: permitir desarrollo local + acceso externo desde cualquier origen
    origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://165.22.186.25:3000",
        "http://165.22.186.25",
        "*",  # Permitir cualquier origen en producción para el frontend
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool for parallel yfinance fetches and scanning (inicializado en lifespan)
executor = None

def get_broker_client():
    """Gets the Alpaca broker client using configured environment variables."""
    api_key = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")
    paper_str = os.getenv("ALPACA_PAPER", "true").lower()
    paper = paper_str == "true"
    
    # 3.1: Check explícito dev/prod — bloquear dinero real en entorno dev
    env_mode = os.getenv("TRADING_ENV", "dev").lower()
    if env_mode == "dev" and not paper:
        logging.critical("🚨 SEGURIDAD: TRADING_ENV=dev pero ALPACA_PAPER=false. Bloqueando acceso a cuenta real.")
        return None
    
    if api_key and secret_key:
        return BrokerClient(api_key, secret_key, paper=paper)
    return None

class ConfigUpdate(BaseModel):
    tickers: str
    interval: str
    period: str
    auto_scan: bool
    auto_trade: bool
    trade_amount: float
    stop_loss_pct: float
    take_profit_pct: float
    use_atr_sl: bool
    kelly_fraction: float
    direction_mode: str
    long_amount: float
    short_amount: float
    long_max_price: float = None
    short_min_price: float = None

@app.get("/api/health")
def health_check():
    db_ok = False
    try:
        if DB_FILE is not None:
            db_ok = os.path.exists(DB_FILE)
    except Exception:
        pass
    return {
        "status": "ok",
        "time": datetime.now().isoformat(),
        "database_connected": db_ok,
        "init_ok": _init_ok,
        "init_errors": _init_errors if not _init_ok else None
    }

@app.get("/api/config")
def get_config_endpoint():
    try:
        config = TradingBrain.get_runtime_config()
        # Fallback values if config keys are missing
        defaults = {
            "tickers": "AAPL, TSLA, MSFT, NVDA, AMZN, GOOGL, META, AMD, NFLX, JPM",
            "interval": "15m",
            "period": "5d",
            "auto_scan": False,
            "auto_trade": False,
            "trade_amount": 100.0,
            "stop_loss_pct": 8.0,
            "take_profit_pct": 15.0,
            "use_atr_sl": True,
            "kelly_fraction": 0.5,
            "direction_mode": "BOTH",
            "long_amount": 100.0,
            "short_amount": 50.0,
            "long_max_price": 0.0,
            "short_min_price": 0.0
        }
        for k, v in defaults.items():
            if k not in config or config[k] is None or (isinstance(v, str) and str(config[k]).strip() == ""):
                config[k] = v
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
def save_config_endpoint(config: ConfigUpdate):
    try:
        config_dict = config.dict()
        # Don't overwrite tickers if the new value is empty
        if not config_dict.get("tickers", "").strip():
            existing = TradingBrain.get_runtime_config()
            config_dict["tickers"] = existing.get("tickers", "SPY, QQQ, AAPL, TSLA, MSFT, NVDA, AMZN, GOOGL, META, AMD")
        # Clean up empty price limits
        if config_dict.get("long_max_price") == 0:
            config_dict["long_max_price"] = None
        if config_dict.get("short_min_price") == 0:
            config_dict["short_min_price"] = None
        TradingBrain.save_runtime_config(config_dict)
        return {"status": "ok", "config": config_dict}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _analyze_ticker_sync(ticker: str, interval: str, period: str, spy_sentiment: int):
    """Worker function to safely fetch and analyze a single ticker."""
    try:
        df = get_stock_data(ticker, period=period, interval=interval)
        if df.empty or len(df) < 50:
            return {"ticker": ticker, "status": "no_data"}
        df_a = apply_strategy(df, spy_sentiment=spy_sentiment, ticker_symbol=ticker)
        latest = df_a.iloc[-1]
        score = int(latest['Score'])
        price = float(latest['Close'])
        p_chg = 0.0
        if len(df_a) > 1:
            p_chg = ((price - df_a['Close'].iloc[-2]) / df_a['Close'].iloc[-2]) * 100

        emoji = "⚪"
        color = "gray"
        if score >= 65:
            emoji = "🟢"
            color = "green"
        elif score <= 35:
            emoji = "🔴"
            color = "red"

        return {
            "ticker": ticker,
            "status": "ok",
            "price": f"${price:,.2f}",
            "change": f"{p_chg:+.2f}%",
            "score": score,
            "emoji": emoji,
            "color": color,
            "ml_pred": f"{df_a.attrs.get('ml_prediction', 50)}%"
        }
    except Exception as e:
        return {"ticker": ticker, "status": "error", "error": str(e)}

@app.get("/api/market-map")
def get_market_map(interval: str = "15m", period: str = "5d"):
    config = TradingBrain.get_runtime_config()
    tickers_str = config.get("tickers", "AAPL, TSLA, MSFT, NVDA, AMZN")
    tickers_list = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]

    spy_sentiment = get_spy_sentiment()
    
    # Run fetches and calculations in parallel with rate limiting
    futures = [
        executor.submit(_rate_limited_fetch, t, interval, period, spy_sentiment)
        for t in tickers_list
    ]
    results = []
    for f in concurrent.futures.as_completed(futures):
        res = f.result()
        if res.get("status") == "ok":
            results.append({
                "ticker": res["ticker"],
                "price": res["price"],
                "change": res["change"],
                "score": str(res["score"]),
                "emoji": res["emoji"],
                "color": res["color"]
            })
        else:
            # Fallback for missing/failed data
            results.append({
                "ticker": res["ticker"],
                "price": "N/A",
                "change": "0.00%",
                "score": "50",
                "emoji": "⚠️",
                "color": "gray"
            })
    # Order alphabetically by ticker symbol
    results.sort(key=lambda x: x["ticker"])
    return results

@app.get("/api/dashboard-state")
def get_dashboard_state(ticker: str = "SPY", interval: str = "15m", period: str = "5d"):
    try:
        config = TradingBrain.get_runtime_config()
        k_frac = config.get("kelly_fraction", 0.5)

        spy_sentiment = get_spy_sentiment()
        df = get_stock_data(ticker, period=period, interval=interval)
        
        if df.empty or len(df) < 50:
            return {
                "ticker": ticker,
                "price": "N/A",
                "change": "0.00%",
                "score": 50,
                "rsi": "N/A",
                "atr": "N/A",
                "kill_switch_label": "Normal",
                "signal_text": "ESPERAR",
                "ml_pred": "50%",
                "ml_label": "NEUTRAL",
                "ml_winrate": "50%",
                "ml_weight": "40%",
                "kelly_size": "N/A",
                "volume_imbalance": "Sin Imbalance",
                "volume_scenario": "Sin datos",
                "reasoning_lines": [f"[{datetime.now().strftime('%H:%M:%S')}] Esperando datos para {ticker}..."]
            }

        df_a = apply_strategy(df, spy_sentiment=spy_sentiment, ticker_symbol=ticker)
        
        latest = df_a.iloc[-1]
        score = int(latest['Score'])
        price = float(latest['Close'])
        atr_val = float(latest['ATR']) if 'ATR' in latest else 0.0
        ml_pred = df_a.attrs.get('ml_prediction', 50)
        k_val = df_a.attrs.get('kelly_size', 0.15) * k_frac
        scenario = latest.get('Market_Scenario', "Estándar")
        rsi_val = float(latest['RSI']) if 'RSI' in latest else 50.0
        z_score = float(latest['Z_Score']) if 'Z_Score' in latest else 0.0
        
        vol_imbalance_up = bool(latest.get('Volume_Imbalance_Up', False))
        vol_imbalance_dn = bool(latest.get('Volume_Imbalance_Down', False))

        try:
            ml_rolling_acc, ml_dynamic_weight = calculate_ml_rolling_accuracy()
        except Exception:
            ml_rolling_acc, ml_dynamic_weight = 0.50, 0.40

        ks_daily = config.get("daily_loss_breaker", False)
        ks_weekly = config.get("weekly_loss_breaker", False)
        kill_switch_label = "🚨 ACTIVO" if (ks_daily or ks_weekly) else "🟢 Normal"

        raw_signal = float(latest.get('Signal', 0.0))
        if raw_signal >= 1.0:
            signal_text = "COMPRAR"
            signal_explain = "Oportunidad de compra institucional detectada."
        elif raw_signal <= -1.0:
            signal_text = "VENDER"
            signal_explain = "Señales de venta/short institucionales detectadas."
        else:
            signal_text = "ESPERAR"
            signal_explain = "Rango o sin señal institucional clara."

        # ML prediction labels
        if ml_pred >= 65:
            ml_label = "OPTIMISTA"
        elif ml_pred <= 35:
            ml_label = "PESIMISTA"
        else:
            ml_label = "NEUTRAL"

        # Volume imbalance state
        volume_imbalance = "Sin Imbalance"
        if vol_imbalance_up:
            volume_imbalance = "🟢 COMPRADOR"
        elif vol_imbalance_dn:
            volume_imbalance = "🔴 VENDEDOR"

        # P&L change
        p_chg = 0.0
        if len(df_a) > 1:
            p_chg = ((price - df_a['Close'].iloc[-2]) / df_a['Close'].iloc[-2]) * 100

        # Construct reasoning logs
        now_str = datetime.now().strftime("%H:%M:%S")
        r_lines = []
        r_lines.append(f"[{now_str}] 📍 Escenario: {scenario}")
        
        if score >= 65:
            r_lines.append(f"[{now_str}] ✅ Score {score}/100 — Señal de Compra Fuerte.")
        elif score <= 35:
            r_lines.append(f"[{now_str}] ⚠️ Score {score}/100 — Señal de Venta Fuerte.")
        else:
            r_lines.append(f"[{now_str}] ⏸️ Score {score}/100 — Zona Neutral de Espera.")

        r_lines.append(f"[{now_str}] 📊 RSI: {rsi_val:.1f} | Z-Score: {z_score:.2f}")
        r_lines.append(f"[{now_str}] 🤖 ML Pred: {ml_pred}% | Acc: {ml_rolling_acc*100:.0f}% | Peso: {ml_dynamic_weight*100:.0f}%")
        
        if vol_imbalance_up:
            r_lines.append(f"[{now_str}] 🌊 Imbalance COMPRADOR detectado en volumen.")
        elif vol_imbalance_dn:
            r_lines.append(f"[{now_str}] 🌊 Imbalance VENDEDOR detectado en volumen.")

        if ks_daily or ks_weekly:
            r_lines.append(f"[{now_str}] 🚨 CIRCUIT BREAKER ACTIVO. Posiciones bloqueadas.")
        else:
            r_lines.append(f"[{now_str}] 🛡️ Gestión Riesgo: OK | Kelly Sizing: {k_val*100:.1f}%")

        return {
            "price": f"${price:,.2f}",
            "change": f"{p_chg:+.2f}%",
            "score": score,
            "rsi": f"{rsi_val:.1f}",
            "atr": f"${atr_val:.2f}",
            "kill_switch_label": kill_switch_label,
            "signal_text": signal_text,
            "ml_pred": f"{ml_pred}%",
            "ml_label": ml_label,
            "ml_winrate": f"{ml_rolling_acc*100:.0f}%",
            "ml_weight": f"{ml_dynamic_weight*100:.0f}%",
            "kelly_size": f"{k_val*100:.1f}%",
            "volume_imbalance": volume_imbalance,
            "volume_scenario": f"Fase 2: {scenario} | 🤖 ML: {ml_label} | VIX: {df_a.attrs.get('macro_vix', 20.0):.1f}",
            "ticker": ticker,
            "reasoning_lines": r_lines
        }
    except Exception as e:
        logging.exception("Error in dashboard state")
        return {"error": str(e)}

@app.get("/api/chart-data")
async def get_chart_data(ticker: str = "SPY", interval: str = "15m", period: str = "5d"):
    try:
        import asyncio as _asyncio

        # Guard contra inicialización lazy: si los módulos aún no cargaron, devolver error claro
        if get_spy_sentiment is None or get_stock_data is None or apply_strategy is None:
            raise HTTPException(status_code=503, detail="Backend inicializando — intente en unos segundos.")

        spy_sentiment = get_spy_sentiment()
        df = get_stock_data(ticker, period=period, interval=interval)
        if df.empty or len(df) < 14:
            raise HTTPException(status_code=404, detail="Not enough data")

        df_a = apply_strategy(df, spy_sentiment=spy_sentiment, ticker_symbol=ticker)

        # Ejecutar el loop de iteración sobre el DataFrame en thread separado
        # para no bloquear el event loop de Uvicorn con Pandas pesado.
        def _build_chart_payload():
            candles = []
            ema20 = []
            ema50 = []
            ema200 = []
            markers = []
            is_daily = interval == "1d"

            for idx, (dt, row) in enumerate(df_a.iterrows()):
                time_val = int(dt.timestamp()) if not is_daily else dt.strftime("%Y-%m-%d")

                candles.append({
                    "time": time_val,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                    "vol_color": "rgba(16,185,129,0.45)" if row["Close"] >= row["Open"] else "rgba(239,68,68,0.45)"
                })

                if "EMA_20" in row and not row.isna()["EMA_20"]:
                    ema20.append({"time": time_val, "value": float(row["EMA_20"])})
                if "EMA_50" in row and not row.isna()["EMA_50"]:
                    ema50.append({"time": time_val, "value": float(row["EMA_50"])})
                if "EMA_200" in row and not row.isna()["EMA_200"]:
                    ema200.append({"time": time_val, "value": float(row["EMA_200"])})

                if "Bullish_Sweep_Signal" in row and row["Bullish_Sweep_Signal"] > 0:
                    markers.append({
                        "time": time_val,
                        "position": "belowBar",
                        "color": "#10b981",
                        "shape": "arrowUp",
                        "text": "Sweep ↑"
                    })
                elif "Bearish_Sweep_Signal" in row and row["Bearish_Sweep_Signal"] > 0:
                    markers.append({
                        "time": time_val,
                        "position": "aboveBar",
                        "color": "#ef4444",
                        "shape": "arrowDown",
                        "text": "Sweep ↓"
                    })

            bull_ob = 0.0
            bear_ob = 0.0
            if "Bullish_OB" in df_a.columns:
                last_valid = df_a[df_a["Bullish_OB"] > 0]
                if not last_valid.empty:
                    bull_ob = float(last_valid["Bullish_OB"].iloc[-1])
            if "Bearish_OB" in df_a.columns:
                last_valid = df_a[df_a["Bearish_OB"] > 0]
                if not last_valid.empty:
                    bear_ob = float(last_valid["Bearish_OB"].iloc[-1])

            return {
                "candles": candles,
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
                "markers": markers,
                "bullish_ob": bull_ob,
                "bearish_ob": bear_ob
            }

        return await _asyncio.to_thread(_build_chart_payload)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ [/api/chart-data] Error para ticker={ticker}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
def get_portfolio_endpoint():
    try:
        bc = get_broker_client()
        if bc and bc.is_connected():
            acc = bc.get_account_info()
            positions = bc.get_open_positions()
            formatted_pos = []
            for p in positions:
                formatted_pos.append({
                    "symbol": p["symbol"],
                    "qty": f"{p['qty']:.4f}".rstrip('0').rstrip('.'),
                    "price": f"${p['current_price']:,.2f}",
                    "pnl": f"${p['unrealized_pl']:+,.2f}",
                    "pnl_pct": f"{p['unrealized_plpc']:+,.2f}%",
                    "side": p["side"].upper()
                })
            result = {
                "connected": True,
                "cached": False,
                "buying_power": f"${acc['buying_power']:,.2f}",
                "equity": f"${acc['equity']:,.2f}",
                "status": acc["status"],
                "positions": formatted_pos
            }
            # Guardar en caché para fallback futuro
            try:
                from core.database import save_bot_state
                save_bot_state({"portfolio_cache": result})
            except Exception:
                pass
            return result
        else:
            logging.warning("⚠️ [/api/portfolio] Broker no conectado — intentando caché...")
            # Intentar recuperar último portfolio desde caché
            try:
                from core.database import load_bot_state
                cached = load_bot_state()
                if cached and "portfolio_cache" in cached:
                    cached["portfolio_cache"]["cached"] = True
                    logging.info("📦 [/api/portfolio] Sirviendo datos cacheados del portfolio.")
                    return cached["portfolio_cache"]
            except Exception:
                pass
            return {
                "connected": False,
                "cached": False,
                "buying_power": "$0.00",
                "equity": "$0.00",
                "status": "Desconectado",
                "positions": [],
                "error": "Broker client credentials not set or incorrect."
            }
    except Exception as e:
        logging.error(f"❌ [/api/portfolio] Error: {e}", exc_info=True)
        # Fallback a caché incluso en error
        try:
            from core.database import load_bot_state
            cached = load_bot_state()
            if cached and "portfolio_cache" in cached:
                cached["portfolio_cache"]["cached"] = True
                cached["portfolio_cache"]["error"] = f"Alpaca error — mostrando último snapshot: {e}"
                logging.info("📦 [/api/portfolio] Fallback a caché tras excepción.")
                return cached["portfolio_cache"]
        except Exception:
            pass
        return {
            "connected": False,
            "cached": False,
            "buying_power": "$0.00",
            "equity": "$0.00",
            "status": "Error",
            "positions": [],
            "error": str(e)
        }

@app.get("/api/trade-history")
def get_trade_history_endpoint():
    try:
        df = get_trade_history(limit=50)
        if df.empty:
            return []
        
        # Format PnL and other columns for JSON/view
        records = []
        for _, row in df.iterrows():
            pnl_val = row.get("pnl")
            pnl_str = "N/A"
            if pnl_val is not None and pnl_val != "" and not (isinstance(pnl_val, float) and row.isna()["pnl"]):
                pnl_str = f"${float(pnl_val):+,.2f}"

            records.append({
                "id": int(row["id"]),
                "fecha": str(row["fecha"]),
                "ticker": str(row["ticker"]),
                "tipo": str(row["tipo"]).upper(),
                "precio": f"${float(row['precio']):,.2f}",
                "cantidad": str(row["cantidad"]),
                "score": int(row["score"]),
                "pnl": pnl_str
            })
        return records
    except Exception as e:
        logging.exception("Error loading trade history")
        return {"error": str(e)}

@app.get("/api/system-status")
def get_system_status_endpoint():
    try:
        config = TradingBrain.get_runtime_config()
        m_open, m_msg = is_market_open()
        
        # Call broker client safely
        open_count = 0
        try:
            bc = get_broker_client()
            if bc and bc.is_connected():
                open_count = len(bc.get_open_positions())
        except Exception:
            pass

        # ML metrics
        try:
            ml_rolling_acc, ml_dynamic_weight = calculate_ml_rolling_accuracy()
            wt_label = f"{ml_rolling_acc*100:.0f}% Win-Rate | Peso: {ml_dynamic_weight*100:.0f}%"
        except Exception:
            wt_label = "No disponible"

        # Cache stats
        cache_stats = {"total_entries": 0, "fresh": 0, "stale": 0}
        try:
            cache_stats = get_cache_stats()
        except Exception:
            pass

        # Background worker health check
        worker_uptime = "Inactivo"
        worker_connected = False
        is_retraining = False
        try:
            resp = requests.get("http://localhost:8001/health", timeout=1)
            if resp.status_code == 200:
                hdata = resp.json()
                uptime_seconds = hdata.get("uptime_seconds", 0)
                worker_uptime = f"Uptime: {uptime_seconds//3600}h {(uptime_seconds%3600)//60}m"
                worker_connected = True
                is_retraining = hdata.get("is_retraining", False)
        except Exception:
            pass

        # Estado del broker (degraded flag del circuit breaker de API)
        broker_degraded = False
        try:
            bcc = get_broker_client()
            if bcc:
                broker_degraded = bcc.degraded
        except Exception:
            pass

        return {
            "market_open": m_open,
            "market_msg": m_msg,
            "scanner_active": config.get("auto_scan", False),
            "autobot_active": config.get("auto_trade", False),
            "positions_count": f"{open_count}/{TradingBrain.MAX_CONCURRENT_POSITIONS}",
            "kill_switch_daily": "🚨 ACTIVO" if config.get("daily_loss_breaker", False) else "🟢 Normal",
            "kill_switch_weekly": "🚨 ACTIVO" if config.get("weekly_loss_breaker", False) else "🟢 Normal",
            "ai_adaptative_label": wt_label,
            "cache_label": f"{cache_stats['total_entries']} entradas ({cache_stats['fresh']} frescas, {cache_stats['stale']} expiradas)",
            "worker_uptime": worker_uptime,
            "worker_connected": worker_connected,
            "is_retraining": is_retraining,
            "broker_degraded": broker_degraded
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/run-scanner")
def run_scanner_endpoint(interval: str = "15m", period: str = "5d"):
    try:
        config = TradingBrain.get_runtime_config()
        tickers_str = config.get("tickers", "AAPL, TSLA, MSFT, NVDA, AMZN")
        tickers_list = [t.strip().upper() for t in tickers_str.split(',') if t.strip()]

        spy_sentiment = get_spy_sentiment()

        # Run scans in parallel with rate limiting
        futures = [
            executor.submit(_rate_limited_fetch, t, interval, period, spy_sentiment)
            for t in tickers_list
        ]
        results = []
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

        # Format results for the frontend view
        formatted_results = []
        for r in results:
            if r.get("status") == "ok":
                score = r["score"]
                signal = "⚪ ESPERAR"
                if score >= 65:
                    signal = "🟢 COMPRAR"
                elif score <= 35:
                    signal = "🔴 VENDER"
                    
                formatted_results.append({
                    "ticker": r["ticker"],
                    "price": r["price"],
                    "score": score,
                    "signal": signal,
                    "ia": r["ml_pred"]
                })
            else:
                formatted_results.append({
                    "ticker": r["ticker"],
                    "price": "N/A",
                    "score": 0,
                    "signal": "⚠️ Error / Sin Datos",
                    "ia": "N/A"
                })

        # Sort by score descending
        formatted_results.sort(key=lambda x: x["score"], reverse=True)
        return formatted_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
