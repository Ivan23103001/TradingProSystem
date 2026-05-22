# 🛰️ REPORTE DE FUENTES E INTELIGENCIA: TradingProSystem v5.0 (Intelligence Revolution)

Este documento es el repositorio de las estrategias de grado institucional implementadas en el sistema.

## 1. FUENTES INTERNAS (Cerebro Central)
*   **`core/brain.py`**: Única fuente de verdad para umbrales SMC, Macro y Riesgo.
*   **`core/strategy.py`**: Motor de ejecución de patrones de alta confluencia.

## 2. ESTRATEGIAS SMC AVANZADAS (Novedades v5.0)
### 2.1 Judas Swing (Falsa Ruptura)
*   **Lógica:** Identificación de barridos de liquidez en los primeros 30-60 min de las aperturas de Londres/NY.
*   **Regla:** Solo operar si hay un barrido previo de un máximo/mínimo local seguido de un desplazamiento (Displacement) en sentido contrario.

### 2.2 Breaker Blocks (Inversión de Estructura)
*   **Lógica:** Un Order Block mitigado que falla y se convierte en soporte/resistencia impulsiva.
*   - **Bullish Breaker:** Un máximo anterior que fue barrido antes de romper la estructura alcista.
*   - **Bearish Breaker:** Un mínimo anterior que fue barrido antes de romper la estructura bajista.

### 2.3 Silver Bullet (Ventanas de Tiempo de Alta Probabilidad)
*   **Horarios Críticos (EST):**
    -   10:00 AM - 11:00 AM (Equity Hour).
    -   02:00 PM - 03:00 PM (Power Hour).
*   **Regla:** Priorizar señales generadas en estas ventanas por su alta probabilidad de llenado de FVG.

## 3. FILTROS MACRO (Sentiment Regime)
### 3.1 DXY Filter (U.S. Dollar Index)
*   **Contexto:** El DXY es el termómetro del "Risk-On / Risk-Off".
*   **Regla de Oro:** Si el DXY tiene una tendencia alcista acelerada (EMA 10 > EMA 21 en 1h), reducir el tamaño de las posiciones un 40% (Cerebro Automático).

### 3.2 VIX Structure (Miedo de Mercado)
*   **Contexto:** No solo importa el nivel, sino la velocidad del cambio.
*   **Regla:** Inhabilitar compras (Longs) si el VIX sube > 5% en una sola sesión o si cruza el umbral de 22.5.

## 4. GESTIÓN DE RIESGO 5.0
*   **Trailing Stop de Volatilidad (ATR):** El Stop Loss se mueve dinámicamente con el precio, pero solo si la volatilidad (ATR) disminuye o el precio se aleja de la zona de entrada.
*   **Bandas de Inacción:** El bot suspende operaciones si el spread del activo supera su promedio de 20 días (Baja liquidez).

---
> [!IMPORTANT]
> Estas estrategias han sido validadas mediante Deep Research y se consideran el estándar para 2026.
