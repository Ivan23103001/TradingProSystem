# 📂 Skill: Lógica Técnica SMC (Smart Money Concepts)

## 📌 Contexto
Este módulo (dentro de `core/strategy.py`) identifica patrones institucionales de alta precisión basados en microestructura de mercado (Smart Money Concepts), evitando la dependencia de osciladores tradicionales.

## 🛠 Componentes del Algoritmo

1. **Order Blocks (OB):** 
    - Identifica la última vela de sentido contrario antes de un fuerte movimiento institucional (`Displacement`).
    - El `Displacement` se confirma cuando el tamaño del cuerpo excede un múltiplo dinámico del ATR (ej: `1.5 * ATR`).
    - **Optimización Vectorizada:** La detección se realiza usando desplazamientos eficientes con pandas `.shift(1).where(...)` para un cálculo instantáneo en todo el DataFrame en lugar de loops iterativos `O(N)`.

2. **Breaker Blocks:**
    - Identifica la inversión de la estructura institucional: un Order Block que falló tras un barrido de liquidez.
    - Se calcula de forma vectorizada comparando el precio de cierre con la ruptura del bloque opuesto previo multiplicado por un umbral de ruptura.

3. **Fair Value Gaps (FVG):**
    - Detecta ineficiencias de precios o vacíos de liquidez entre tres velas consecutivas (High de vela $t-2$ vs Low de vela $t$, o viceversa).
    - Representa zonas de alta atracción magnética donde el mercado tiende a rellenar órdenes pendientes.

4. **Liquidity Sweeps (Barridos):**
    - Detecta barridos de stops (Judas Swing) cuando mechas largas perforan soportes o resistencias locales (lookback: 20 periodos) y cierran rápidamente dentro del rango operativo.

5. **Volume Profile POC:**
    - Determina el Point of Control (POC) local mediante bins de precios ponderados por volumen para encontrar la zona de mayor interés comercial.
    - **v5.1 — Vectorizado con rolling().apply():** `calculate_volume_profile()` usa `pd.DataFrame(...).rolling(window=lookback).apply(lambda w: _poc_of_window(...))` completamente vectorizado. Queda **terminantemente prohibido** reintroducir loops `for` en esta función.

6. **Volume Imbalances (Order Flow):**
    - Filtra zonas con volumen institucional sustancialmente superior al promedio (ej: `> 1.8x` de media móvil de 20 periodos), validando la participación algorítmica.

## 🚀 Optimización Extrema de Rendimiento (Fase 2)
Para lograr un **speedup de ~10x** y permitir escaneos rápidos de watchlists masivas en menos de 5 segundos, el motor realiza las siguientes optimizaciones:
- **Pre-computación Rodante Vectorizada:** Todas las ventanas de búsqueda de bloques y gaps (`Bullish_OB`, `Bearish_OB`, `FVG_Bullish`, `FVG_Bearish`, `Volume_Imbalance`) se calculan con operaciones vectorizadas de pandas utilizando `.rolling(window=X, min_periods=1).max().shift(1)` antes del loop.
- **Acceso Directo $O(1)$:** En cada vela, el motor accede a los valores de soporte e históricos en tiempo de ejecución constante $O(1)$ a través de los vectores pre-calculados, reduciendo el coste de operaciones repetitivas.
- **Formateo de Tiempos Pre-indexado:** Los índices de fecha y hora se formatean de forma vectorizada antes de iniciar el loop de análisis.
- **Volume Profile Vectorizado (v5.1):** `calculate_volume_profile()` sin loops — reemplazado por `rolling().apply()` de pandas para cumplir con el mandato de vectorización total.

## ⚙️ Reglas de Modificación
- Mantener los métodos de detección completamente vectorizados. No reintroducir loops `for` o consultas individuales a la base de datos dentro del loop de candle.
- Para ajustar la sensibilidad del `Displacement`, modificar `smc_atr` en los parámetros de la clase `TradingBrain`.
- **VIX Threshold con Default:** La línea `threshold = next(t for vmax, t in VIX_SCORE_THRESHOLDS if vix_level < vmax)` usa `next(..., default=75)` para evitar `StopIteration` si VIX >= 99.