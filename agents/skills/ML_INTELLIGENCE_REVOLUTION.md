# 📂 Skill: Inteligencia Artificial Adaptativa (ML Engine Avanzado)

## 📌 Contexto
Ubicado en `core/ml_engine.py` e integrado en `core/strategy.py`. El sistema utiliza una arquitectura de **Ensamble Híbrido (Random Forest + Gradient Boosting)** y un **Tracker de Rendimiento Rodante (Walk-Forward Meta-Learning)** para regular dinámicamente el peso de las predicciones de IA según su tasa de éxito real en el broker.

## 🛠 Arquitectura del Modelo
1. **Tipo de Ensamble Híbrido:**
    - **Random Forest Classifier (Bagging):** Reduce la varianza y evita el overfitting sobre el ruido diario del mercado.
    - **Gradient Boosting Classifier (Boosting):** Minimiza el sesgo y captura con precisión relaciones no lineales complejas y secuenciales de la tendencia.
2. **Preprocesamiento Robusto (Robust Scaling):**
    - Se implementó un `RobustScaler` antes del entrenamiento y la inferencia para normalizar las features utilizando la mediana y los rangos intercuartílicos. Esto hace que el modelo sea inmune a picos anormales de volatilidad y outliers del mercado financiero.
3. **Predicción Ensamble (Probability Averaging):**
    - El modelo promedia las probabilidades estimadas por ambos clasificadores. Si el ensamble predice `>= 75%`, indica una fuerte convicción alcista; si predice `<= 25%`, una fuerte convicción bajista.
4. **Cerebro Adaptativo (Dynamic Weighting):**
    - El sistema monitorea de forma autónoma la base de datos de transacciones cerradas (`trade_history.db`) analizando la precisión (Win-Rate) real de la IA sobre los últimos 15 trades.
    - **Ajuste Dinámico de Pesos:**
        - **Alta Precisión (`>= 65%`):** El peso de la IA en la estrategia final aumenta al **55%**, priorizando sus decisiones.
        - **Precisión Normal (`50% - 65%`):** Peso estándar del **40%**.
        - **Baja Precisión / Regime Shift (`< 50%`):** El peso se reduce automáticamente al **15%** para proteger el capital contra rachas de pérdida de la IA (Model Decay / Cambio de Régimen).

## 🚀 Adaptabilidad Temporal de Objetivos (Fase 2)
El motor de features de ML ahora es completamente paramétrico y adapta la definición del objetivo (Target) según la escala del timeframe que opera el bot. Esto evita la discrepancia lógica de entrenar en diario y predecir en 15m.
- **Definición Dinámica de Movimiento Limpio:** Un objetivo exitoso (`Target = 1`) requiere que el precio suba al menos `min_move_pct` dentro de las siguientes `bars_forward` velas, **sin** caer en ningún momento por debajo de una barrera de stop loss proporcional definida como `min_move_pct / 2.0`.
- **v5.1 — Forward Low sin Doble Shift:** El cálculo del Target usa `forward_low` obtenido con rolling inverso (`data['Low'].iloc[::-1].rolling(bars_forward+1).min().iloc[::-1]`). Esto evita el `shift(-bars_forward)` anidado que desperdiciaba `2*bars_forward` filas de entrenamiento. Ahora solo se pierden `bars_forward` filas.
- **Configuraciones de Escala Recomendadas:**
    - **Velas Diarias (1d):** `bars_forward=3`, `min_move_pct=0.015` (1.5% de subida, max 0.75% de retroceso)
    - **Velas de 15m:** `bars_forward=6`, `min_move_pct=0.005` (0.5% de subida, max 0.25% de retroceso)
    - **Velas de 5m:** `bars_forward=12`, `min_move_pct=0.003` (0.3% de subida, max 0.15% de retroceso)

## ⚙️ Reglas de Modificación
- **Parámetros Explícitos:** Siempre que se invoque `train_trading_model()` o `prepare_features()`, se deben suministrar explícitamente los parámetros `bars_forward` y `min_move_pct` correspondientes a la escala de datos utilizada.
- **Normalización Obligatoria:** Todos los nuevos indicadores o features deben pasar por el pipeline de `scaler` guardado en el archivo `.pkl`.
- **Sincronización de Base de Datos:** `bot_worker.py` debe registrar puntualmente el PnL y exit price en la DB usando `update_last_trade_pnl` para que el cerebro adaptativo cuente con datos precisos de Win-Rate.
- **Entrenamiento Dominical Consolidado (v5.1):** El re-entrenamiento semanal recolecta datos de todos los tickers de la watchlist, los consolida con `pd.concat()` y entrena **un solo modelo combinado**. Queda prohibido entrenar un modelo por ticker (sobreescribiría el archivo `.pkl` N veces).
- **Forward Low sin Doble Shift (v5.1):** El Target debe calcularse con `forward_low` vía rolling inverso, no con `shift(-bars_forward)` anidado dentro de otro `shift()`.

## 🔄 Versionado de Modelos, Backups y Rollback
1. **Versionado de Dependencias:** El archivo del modelo guarda explícitamente `'sklearn_version'` y `'trained_at'` (timestamp). Al cargar el modelo en inferencia, se comprueba si la versión actual de scikit-learn coincide con la que entrenó el modelo y emite una advertencia si hay diferencia para prevenir fallos silenciosos por incompatibilidad de bytes.
2. **Backups en Re-entrenamiento:** Antes de guardar o sobreescribir el archivo `ml_trading_model.pkl`, el motor copia el modelo actual en `model_backups/ml_model_YYYYMMDD_HHMM.pkl` de manera automática y realiza una limpieza rotativa manteniendo únicamente los 3 backups más recientes.
3. **Rollback Rápido:** Existe la utilidad `restore_model.py` en la raíz del proyecto para restaurar de inmediato el último backup válido (o uno específico pasado por parámetro) en caso de que el nuevo modelo presente fallos de precisión o rendimiento.
4. **Firma HMAC-SHA256 (v5.1):** Tras `joblib.dump()`, el motor genera `ml_trading_model.pkl.sig` con firma HMAC-SHA256 derivada del machine-id del sistema. `get_ml_prediction()` ejecuta `_verify_integrity()` antes de `joblib.load()`. Modelos con firma inválida se rechazan retornando 50 (neutro).
5. **Carga Segura de Modelos Legacy (v5.1):** `get_ml_prediction()` usa `saved.get('model')` con verificación explícita `if model is None` para evitar `KeyError` en dicts legacy corruptos. Modelos sin `'rf_model'` ni `'model'` se tratan como corruptos.

## 🔗 Integración con API Backend (v5.1)
- **Rutas /api/v1 Idempotentes:** Los endpoints de ML expuestos en `backend/main.py` (dashboard-state, chart-data, market-map, scanner) se clonan automáticamente a `/api/v1/*`. La clonación usa guard `"/api/v1" not in _path` + deduplicación para prevenir `/api/v1/api/v1/...`. Esto aplica también al health check del worker (`/health` en puerto 8001) que no se clona por estar en proceso separado.
