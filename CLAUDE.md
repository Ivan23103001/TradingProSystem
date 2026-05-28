# 📊 Trading Pro System (TPS) — Contexto Maestro

## 🎯 Visión del Proyecto
Sistema de trading algorítmico institucional basado en **Smart Money Concepts (SMC)**, Machine Learning (Random Forest) y Gestión de Riesgo Cuantitativa (Kelly). El bot está diseñado para escanear activos, identificar zonas de oferta/demanda y ejecutar operaciones automáticas con convicción probabilística.

## 🛠 Pila Tecnológica (Tech Stack)
- **Lenguaje:** Python 3.10+
- **Frontend/UI:** Streamlit (vibrante, oscuro, premium).
- **Análisis Técnico:** `ta-lib` / `ta` (Python Library).
- **IA/ML:** `scikit-learn` (Random Forest Classifier).
- **Base de Datos:** SQLite (Historial de trades y logs).
- **Ejecución:** Alpaca Trading API (opcional: soporte para MT5 en el futuro).
- **Visualización:** Plotly (Gráficos interactivos de velas).

## 📁 Arquitectura del Proyecto
- `/core/`: Lógica pesada.
    - `strategy.py`: Cálculo de indicadores, SMC, Z-Score y Score de Convicción.
    - `ml_engine.py`: Entrenamiento y predicción del modelo Random Forest.
    - `broker.py`: Abstracción de órdenes de compra/venta.
    - `database.py`: Gestión de la base de datos `trade_history.db`.
    - `telegram_listener.py`: Escuchador interactivo en tiempo real para recibir y responder comandos de Telegram de forma segura.
- `bot_worker.py`: El "proceso obrero" que corre en segundo plano para el Auto-Trading. Inicia el escuchador de Telegram en segundo plano.
- `app.py`: Interfaz principal y scanner en tiempo real.
- `FUENTES_INTELIGENCIA.md`: Repositorio de estrategias y hallazgos del Deep Research.

## 🚨 Reglas Críticas (No modificar sin aprobación)
1. **Lógica de Riesgo:** No alterar los cálculos del *Criterio de Kelly* o el *ATR-based Stop Loss* en `core/strategy.py` sin pruebas exhaustivas.
2. **Nomenclatura SMC:** Mantener estrictamente el lenguaje de ICT/SMC: *Order Blocks (OB)*, *Fair Value Gaps (FVG)*, *Liquidity Sweeps*.
3. **UI/UX:** El diseño debe ser siempre Premium (modo oscuro, gradientes, tipografías modernas). Consultar siempre `ui/styles.py`.
4. **Manejo de Errores:** Todas las llamadas a la API o DB deben tener bloques `try-except` con logging adecuado.
5. **Seguridad de Telegram:** El escuchador de Telegram debe restringir las respuestas exclusivamente al `TELEGRAM_CHAT_ID` autorizado en el archivo `.env`. No responder a mensajes de chats no autorizados.
6. **Sincronización Obligatoria (SYNC):** Antes de finalizar cualquier cambio, se DEBE verificar el cumplimiento del `SYNC_PROTOCOL.md` para asegurar que el Frontend, el Backend y el Cerebro estén actualizados y en armonía.

## 💻 Comandos de Uso
- **Iniciar Interfaz:** `streamlit run app.py`
- **Iniciar Bot Automático (Worker):** `python bot_worker.py`
- **Probar Conexión:** `python check_conn.py`
- **Ver Estado del Bot:** `python check_status.py`
- **Probar Escuchador de Telegram:** `$env:PYTHONPATH="."; python scratch/test_telegram_listener.py`

---
> [!IMPORTANT]
> Antes de realizar cualquier "Deep Research" o modificación mayor, consultar siempre los archivos en `.agents/skills/` para entender la lógica profunda de cada módulo.
