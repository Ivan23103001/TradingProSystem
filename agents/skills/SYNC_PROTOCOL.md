# 📂 Skill: Protocolo de Sincronización Frontend & Backend

## 📌 Contexto
Este protocolo es de cumplimiento obligatorio para cualquier IA o humano que trabaje en el proyecto. Su objetivo es evitar que se añadan funciones poderosas en el código (Backend) que no sean visibles o ajustables en la interfaz (Frontend), y viceversa.

## 🛠 Las 5 Capas de Sincronización (v5.1)
Para cualquier cambio, mejora o nueva función:

1. **CAPA 1: El Cerebro (`core/brain.py`)**
    - Definir los umbrales o constantes en la clase `TradingBrain`.
    - Añadir el parámetro al pool de `get_technical_params()`.
2. **CAPA 2: El Backend (`core/strategy.py`, `core/ml_engine.py`)**
    - Implementar la lógica matemática o de detección.
    - Asegurarse de que el código pida los parámetros al `Brain` y no use valores estáticos.
3. **CAPA 3: El Frontend React (`frontend/src/`) — 🆕 v5.1**
    - Añadir controles UI (sliders, toggles, métricas) en `Dashboard.tsx` para que el usuario pueda ver o modificar la nueva función.
    - Actualizar la "Consola de Decisión" (`reasoning_lines`) para que el bot informe cuándo se está usando esa función.
    - **Regla de `API_BASE`:** `apiConfig.ts` debe usar rutas relativas (`""`) en producción. `VITE_API_URL=` en `.env.production`. Nunca hardcodear IPs o `localhost`.
    - **Regla de Null Safety:** Todo acceso a datos de la API debe usar optional chaining (`?.`) y nullish coalescing (`??`). Ver `Dashboard.tsx` para el patrón.
4. **CAPA 4: Nginx Reverse Proxy (`nginx-tradingpro.conf`) — 🆕 v5.1**
    - Si se añade un nuevo endpoint en el backend, verificar que Nginx no necesite ajustes de timeout o buffering.
    - `proxy_buffering off` solo debe aplicarse a endpoints de respuestas grandes (`/api/chart-data`), no globalmente.
    - Asegurar que los bloques `deny all` para archivos sensibles sigan cubriendo nuevas extensiones.
5. **CAPA 5: El Frontend Streamlit Legacy (`app.py`, `ui/styles.py`)**
    - Añadir controles (sliders, toggles o métricas) para que el usuario pueda ver o modificar la nueva función en la interfaz legacy.
    - Actualizar la "Consola de Razonamiento" para que el bot informe cuándo se está usando esa función.

## ⚙️ Reglas de Validación
- **REGLA DE ORO:** Si un parámetro no está en el frontend (React o Streamlit), no debe estar "hardcoded" en `strategy.py`.
- **REGLA DE LOGS:** Si el bot toma una decisión basada en una nueva regla, debe registrarla en el `worker.log` y mostrarla en la consola de razonamiento del dashboard.
- **REGLA DE PERSISTENCIA:** Si se añade una opción en la UI, esta debe guardarse en el `bot_config.json` a través de `save_config()`.
- **REGLA DE API_BASE (v5.1):** El frontend React debe usar rutas relativas. `API_BASE` en `apiConfig.ts` debe ser `""` en producción. El archivo `.env.production` debe tener `VITE_API_URL=` (vacío). Esto asegura que las peticiones fluyan a través de Nginx sin problemas de CORS o mixed-content.
- **REGLA DE NULL SAFETY (v5.1):** Todo `fetch().then(json => ...)` debe asumir que los campos pueden ser `undefined`. Usar `data.field?.method() ?? fallback`.

## 🌐 Reglas para la API Backend (v5.1)
- **RATE LIMITING EN YFINANCE:** Todo endpoint que llame a `get_stock_data()` o `apply_strategy()` debe usar el wrapper `_rate_limited_fetch()` definido en `backend/main.py`. Este wrapper impone un semáforo de máximo 5 requests concurrentes y un delay mínimo de 300ms entre llamadas. Queda prohibido lanzar requests a yfinance sin pasar por este wrapper.
- **AUTENTICACIÓN:** `POST /api/config` requiere header `X-API-Key`. La clave se lee de la variable de entorno `TRADING_API_KEY` (`.env`). No se deben crear nuevos endpoints de escritura sin protegerlos con el mismo middleware.
- **DEV/PROD CHECK:** Cualquier código que instancie `BrokerClient` debe verificar que si `TRADING_ENV=dev`, no se use `ALPACA_PAPER=false`. Usar `get_broker_client()` como punto único de construcción.
- **IDEMPOTENCIA /api/v1 (v5.1):** La clonación de rutas debe usar el guard `"/api/v1" not in _path` + `any(r.path == _v1_path)` de deduplicación. No modificar sin entender el mecanismo de recarga de módulos.

## 🔄 Flujo de una Petición (v5.1)
```
Navegador → GET /api/dashboard-state?ticker=SPY
    ↓
Nginx (puerto 80) → location /api/ → proxy_pass http://127.0.0.1:8000
    ↓
Uvicorn (puerto 8000) → backend/main.py → @app.get("/api/dashboard-state")
    ↓
core/strategy.py → core/data_fetcher.py → yfinance API
    ↓
Respuesta JSON → Nginx → Navegador
    ↓
Dashboard.tsx → data.change?.startsWith("+") ?? false → render ✅
```

---
> [!IMPORTANT]
> Antes de terminar cualquier tarea, la IA DEBE confirmar: "¿He sincronizado las 5 capas (Brain → Backend → React → Nginx → Streamlit Legacy) con el nuevo cambio?"

> [!WARNING]
> Nunca hardcodear `localhost` o IPs en el frontend. Usar rutas relativas. La variable `VITE_API_URL` en `.env.production` debe estar vacía (`VITE_API_URL=`).