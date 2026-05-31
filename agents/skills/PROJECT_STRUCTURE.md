# 📂 Skill: Estructura del Proyecto y Relaciones de Componentes

## 📌 Contexto
Este documento sirve como mapa arquitectónico del proyecto `TradingProSystem`. Es de suma importancia entender cómo interactúan los componentes para evitar romper dependencias al realizar modificaciones.

## 🗺️ Mapa del Directorio del Proyecto
```
TradingProSystem/
│
├── agents/
│   └── skills/                  # "Memoria" y directrices para agentes de IA
│       ├── ML_INTELLIGENCE_REVOLUTION.md
│       ├── RISK_MANAGEMENT_MASTER.md
│       ├── SMC_TECHNICAL_LOGIC.md
│       ├── SYSTEM_INTEGRITY.md
│       ├── SYNC_PROTOCOL.md
│       └── PROJECT_STRUCTURE.md
│
├── core/                        # Núcleo del Backend
│   ├── brain.py                 # Cerebro central: constantes, parámetros y riesgo
│   ├── config.py                # Proxy de lectura/escritura de configuraciones
│   ├── database.py              # Acceso seguro SQLite con pool thread-local y modo WAL
│   ├── ml_engine.py             # Ensamble de predicción (RF + GB), firma HMAC y backups
│   ├── strategy.py              # Lógica SMC, indicadores vectorizados y generación de señales
│   ├── telegram_listener.py     # Escuchador interactivo en tiempo real de Telegram (24/7)
│   ├── notifier.py              # Notificador Telegram no bloqueante (hilo daemon)
│   ├── data_fetcher.py          # Descarga con caché TTL y fallback stale
│   ├── broker.py                # Cliente Alpaca (órdenes, posiciones, cuenta)
│   ├── simulator.py             # Verificación de mercado abierto y horarios críticos
│   └── health_server.py         # Servidor FastAPI ligero para health checks (puerto 8001)
│
├── backend/
│   └── main.py                  # API REST FastAPI (puerto 8000) con auth, rate-limit y dev/prod checks
│
├── ui/                          # Estilado y assets de la UI
│   └── styles.py                # CSS y temas de Streamlit
│
├── tests/                       # Suite de pruebas automatizadas con pytest
│   └── ...
│
├── scratch/                     # Scripts temporales de prueba y desarrollo
│   └── test_telegram_listener.py # Script de prueba del bot interactivo
│
├── app.py                       # Interfaz Gráfica (Streamlit)
├── bot_worker.py                # Hilo principal de ejecución de trading (24/7) con paralelismo
├── restore_model.py             # Herramienta de Rollback del modelo ML
├── patch_app.py                 # Parcheador de app.py con backup atómico y rollback
├── requirements.txt             # Dependencias del proyecto fijadas
├── bot_config.json              # Configuración persistente del usuario en tiempo de ejecución
└── ml_trading_model.pkl / .sig  # Modelo ML serializado + firma HMAC-SHA256
```

## 🛠️ Roles de los Componentes y Flujos de Datos

### 1. El Cerebro Central (`core/brain.py`)
- **Rol:** Centraliza todas las variables de riesgo, multiplicadores SMC, y umbrales globales.
- **Acceso:** Todas las clases de lógica técnica o visual leen de aquí en lugar de usar valores hardcoded.
- **Paths Absolutos:** Define el directorio raíz del proyecto (`_BASE_DIR`) dinámicamente y expone rutas absolutas para la base de datos, el archivo de configuración y el modelo de ML, garantizando un inicio seguro como servicio daemon.

### 2. Gestión de Datos (`core/database.py`)
- **Rol:** Centraliza el acceso a SQLite. Habilita el modo WAL (Write-Ahead Logging) y timeouts elevados (15s) para permitir lecturas y escrituras seguras concurrentes.
- **v5.1 — Pool Thread-Local:** `get_connection()` ahora reutiliza una conexión persistente por hilo mediante `threading.local()`. Las funciones `save_trade`, `save_equity`, `get_trade_history`, `get_equity_history`, `update_last_trade_pnl` y `archive_old_trades` **no cierran** la conexión tras su uso. Queda prohibido llamar a `conn.close()` manualmente en código que use este módulo.
- **Flujo:** 
  - `bot_worker.py` escribe trades y equity.
  - `backend/main.py` y `telegram_listener.py` leen el historial.
  - Todos comparten la misma pool thread-local sin contención de apertura/cierre.

### 3. Motor de Inteligencia Artificial (`core/ml_engine.py`)
- **Rol:** Entrena y ejecuta inferencias del Ensamble Híbrido (Random Forest + Gradient Boosting) con preprocesamiento `RobustScaler` de `scikit-learn` y maneja una carpeta rotativa de copias de seguridad de modelos anteriores.
- **v5.1 — Seguridad Pickle:** Firma HMAC-SHA256 en `.pkl.sig` derivada del machine-id. `get_ml_prediction()` verifica integridad antes de `joblib.load()`. Modelos legacy sin `'rf_model'` ni `'model'` se tratan como corruptos.

### 4. Lógica de Trading (`core/strategy.py`)
- **Rol:** Detecta patrones SMC (Order Blocks, Liquidity Sweeps, Imbalances) y calcula las señales de trading combinando indicadores tradicionales y la inferencia de `core/ml_engine.py`.
- **v5.1 — Optimizaciones:** Volume Profile vectorizado con `rolling().apply()`, VIX threshold con `default=75`, HTF cache con guardado incluso en fallo para evitar reintentos.

### 5. Frontend UI (`app.py`)
- **Rol:** Dashboard interactivo para ver balances, gráficos interactivos con Plotly, logs, y ajustar parámetros en tiempo de ejecución de manera visual.

### 6. Ejecución en Producción (`bot_worker.py`)
- **Rol:** Script daemon en segundo plano que corre indefinidamente. Realiza descargas con yfinance en paralelo (ThreadPoolExecutor), calcula señales con `strategy.py`, efectúa ejecuciones en Alpaca de forma asíncrona, guarda registros en base de datos e inicia el escuchador de Telegram en segundo plano.
- **v5.1 — Validación de Tickers:** Filtra tickers con regex `^[A-Z0-9\.\-]{1,10}$` antes de procesarlos.

### 7. Escuchador de Telegram (`core/telegram_listener.py`)
- **Rol:** Servidor interactivo en segundo plano (hilo daemon) que realiza sondeos a Telegram (`getUpdates`). Responde a comandos del usuario en tiempo real (`/estado`, `/balance`, `/historial_hoy`) con un estricto filtro de seguridad que bloquea cualquier ID no autorizado.

### 8. Notificador Telegram (`core/notifier.py`)
- **Rol:** Envía alertas de trading en background sin bloquear el hilo principal.
- **v5.1 — No Bloqueante:** `send_message()` lanza un hilo daemon interno. Timeouts de red en Telegram no retrasan el loop de trading.

### 9. API Backend (`backend/main.py`)
- **Rol:** API REST FastAPI en puerto 8000 para el frontend web. Expone endpoints de configuración, escaneo, chart data, portfolio y system status.
- **v5.1 — Seguridad:** Middleware de autenticación API Key en `POST /api/config`. Bloqueo explícito dev/prod: rechaza conexiones reales si `TRADING_ENV=dev`. Rate limiting en yfinance con semáforo (máx 5 concurrentes) y delay de 300ms entre requests.

---
> [!NOTE]
> Al agregar o cambiar cualquier característica, debes identificar a qué componente pertenece y verificar que sus puertos de entrada/salida (parámetros y llamadas) se sincronicen de acuerdo al [Protocolo de Sincronización](file:///.agents/skills/SYNC_PROTOCOL.md).