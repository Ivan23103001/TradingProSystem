# 📊 Trading Pro System (TPS) — Contexto Maestro v5.3

## 🎯 Visión del Proyecto
Sistema de trading algorítmico institucional basado en **Smart Money Concepts (SMC)**, Machine Learning (Random Forest + Gradient Boosting) y Gestión de Riesgo Cuantitativa (Kelly). El bot está diseñado para escanear activos, identificar zonas de oferta/demanda y ejecutar operaciones automáticas con convicción probabilística.

## 🛠 Pila Tecnológica (Tech Stack)
- **Lenguaje:** Python 3.12+ (VPS) / Python 3.14+ (dev)
- **Backend API:** FastAPI + Uvicorn (puerto 8000)
- **Frontend:** React + Vite + TypeScript + Tailwind + lightweight-charts
- **Análisis Técnico:** `ta` (Python Library), `yfinance`
- **IA/ML:** `scikit-learn` (Random Forest Classifier + Gradient Boosting)
- **Base de Datos:** SQLite en modo WAL con pool thread-local
- **Ejecución:** Alpaca Trading API (paper/live)
- **Visualización:** lightweight-charts (frontend), Plotly (Streamlit legacy)
- **Proxy Inverso:** Nginx (HTTPS/TLS 1.3 + HSTS)
- **Process Manager:** PM2 (ecosystem.config.js)
- **Notificaciones:** Telegram Bot API (MarkdownV2)

## 📁 Arquitectura del Proyecto
- `/core/`: Lógica pesada — motor del sistema.
    - `brain.py`: Cerebro central v5.3 — 7 secciones documentadas (SMC, Risk, Direction, Macro, Timing, ML, Static Methods)
    - `config.py`: Proxy de lectura/escritura de configuraciones vía TradingBrain
    - `database.py`: Acceso seguro SQLite con pool thread-local, modo WAL, type hints PEP 484
    - `ml_engine.py`: Ensamble RF+GB con RobustScaler, firma HMAC-SHA256, `ML_SIGNING_SECRET` configurable
    - `strategy.py`: Lógica SMC vectorizada, Kelly normalizado a %, type hints PEP 484
    - `telegram_listener.py`: Escuchador interactivo Telegram con Long Polling y chat ID verification
    - `notifier.py`: Notificador Telegram no bloqueante (MarkdownV2)
    - `data_fetcher.py`: Descarga con caché TTL 45s, fallback stale, type hints
    - `broker.py`: Cliente Alpaca con _safe_api_call (exponential backoff + jitter)
    - `simulator.py`: Verificación de mercado abierto, horarios críticos, Monte Carlo
    - `health_server.py`: Servidor FastAPI ligero para health checks (puerto 8001)
- `/backend/`:
    - `main.py`: API REST FastAPI (puerto 8000) — CORS, API Key auth, rate limiting, clonación /api/v1
    - `init_modules.py`: Inicialización lazy de 7 módulos core (extraído de main.py para reducir tamaño)
- `bot_worker.py`: Loop principal 24/7 con ThreadPoolExecutor reutilizado, IMP-0 (no reintentar posiciones abiertas), SL/TP software, post-mortem analysis, auto-retrain dominical
- `/frontend/`: React/Vite SPA con Dashboard, TradingChart, market map, portfolio, system status
- `nginx-tradingpro.conf`: Nginx con HTTPS 443, TLS 1.2/1.3, HTTP/2, HSTS, OCSP stapling, rate limiting
- `ecosystem.config.js`: PM2 para tps-backend (:8000) + tps-worker (bot_worker.py)
- `bot_config.json`: Configuración runtime (tickers, montos, SL/TP, direction mode)
- `.env`: Variables de entorno (Alpaca, Telegram, API Key, ML_SIGNING_SECRET) — NO committear
- `FUENTES_INTELIGENCIA.md`: Repositorio de estrategias y hallazgos del Deep Research

## 🚨 Reglas Críticas (No modificar sin aprobación)
1. **Lógica de Riesgo:** No alterar los cálculos del *Criterio de Kelly* (normalizado a %) o el *ATR-based Stop Loss* en `core/strategy.py` sin pruebas exhaustivas.
2. **Nomenclatura SMC:** Mantener estrictamente el lenguaje de ICT/SMC: *Order Blocks (OB)*, *Fair Value Gaps (FVG)*, *Liquidity Sweeps*.
3. **UI/UX:** El diseño debe ser siempre Premium (modo oscuro, gradientes, tipografías modernas).
4. **Manejo de Errores:** Todas las llamadas a la API o DB deben tener bloques `try-except` con logging adecuado.
5. **Seguridad de Telegram:** El escuchador de Telegram debe restringir las respuestas exclusivamente al `TELEGRAM_CHAT_ID` autorizado en el archivo `.env`.
6. **Sincronización Obligatoria (SYNC):** Antes de finalizar cualquier cambio, se DEBE verificar el cumplimiento del `SYNC_PROTOCOL.md` para asegurar que el Frontend, el Backend y el Cerebro estén actualizados y en armonía.
7. **Seguridad SQL:** Todas las consultas SQL deben usar parámetros `?` (parametrized queries). Prohibidos los f-strings en SQL.
8. **ThreadPoolExecutor:** Reutilizar el executor en bot_worker.py. No crear/destruir uno nuevo por ciclo.
9. **HTTPS:** El tráfico de producción debe ir por HTTPS (dominio DuckDNS + Let's Encrypt).

## 💻 Comandos de Uso
- **Iniciar Backend:** `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- **Iniciar Bot Automático (Worker):** `python bot_worker.py`
- **PM2 (producción):** `pm2 start ecosystem.config.js`
- **PM2 restart:** `pm2 restart all`
- **Probar Conexión:** `python scripts/check_conn.py`
- **Ver Estado del Bot:** `python scripts/check_status.py`
- **Verificar P&L:** `python scripts/check_pnl.py`
- **Entrenar ML:** `python scripts/train_ai.py`
- **Tests:** `python -m pytest tests/ -v`
- **Frontend build:** `cd frontend && npm run build`

---
> [!IMPORTANT]
> Antes de realizar cualquier modificación mayor, consultar los archivos en `.agents/skills/` para entender la lógica profunda de cada módulo.