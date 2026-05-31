# 📂 Skill: Protocolo de Sincronización Frontend & Backend

## 📌 Contexto
Este protocolo es de cumplimiento obligatorio para cualquier IA o humano que trabaje en el proyecto. Su objetivo es evitar que se añadan funciones poderosas en el código (Backend) que no sean visibles o ajustables en la interfaz (Frontend), y viceversa.

## 🛠 Las 3 Capas de Sincronización
Para cualquier cambio, mejora o nueva función:

1. **CAPA 1: El Cerebro (`core/brain.py`)**
    - Definir los umbrales o constantes en la clase `TradingBrain`.
    - Añadir el parámetro al pool de `get_technical_params()`.
2. **CAPA 2: El Backend (`core/strategy.py`, `core/ml_engine.py`)**
    - Implementar la lógica matemática o de detección.
    - Asegurarse de que el código pida los parámetros al `Brain` y no use valores estáticos.
3. **CAPA 3: El Frontend (`app.py`, `ui/styles.py`)**
    - Añadir controles (sliders, toggles o métricas) para que el usuario pueda ver o modificar la nueva función.
    - Actualizar la "Consola de Razonamiento" para que el bot informe cuándo se está usando esa función.

## ⚙️ Reglas de Validación
- **REGLA DE ORO:** Si un parámetro no está en `app.py`, no debe estar "hardcoded" en `strategy.py`.
- **REGLA DE LOGS:** Si el bot toma una decisión basada en una nueva regla, debe registrarla en el `worker.log` y mostrarla en el Streamlit.
- **REGLA DE PERSISTENCIA:** Si se añade una opción en la UI, esta debe guardarse en el `bot_config.json` a través de `save_config()`.

## 🌐 Reglas para la API Backend (v5.1)
- **RATE LIMITING EN YFINANCE:** Todo endpoint que llame a `get_stock_data()` o `apply_strategy()` debe usar el wrapper `_rate_limited_fetch()` definido en `backend/main.py`. Este wrapper impone un semáforo de máximo 5 requests concurrentes y un delay mínimo de 300ms entre llamadas. Queda prohibido lanzar requests a yfinance sin pasar por este wrapper.
- **AUTENTICACIÓN:** `POST /api/config` requiere header `X-API-Key`. La clave se lee de `bot_config.json` (campo `api_key`) o de `TRADING_API_KEY` en `.env`. No se deben crear nuevos endpoints de escritura sin protegerlos con el mismo middleware.
- **DEV/PROD CHECK:** Cualquier código que instancie `BrokerClient` debe verificar que si `TRADING_ENV=dev`, no se use `ALPACA_PAPER=false`. Usar `get_broker_client()` como punto único de construcción.

---
> [!IMPORTANT]
> Antes de terminar cualquier tarea, la IA DEBE confirmar: "¿He sincronizado el Frontend con el nuevo cambio del Backend?"