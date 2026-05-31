# 📂 Skill: Gestión de Riesgo Maestra (Risk & Kelly)

## 📌 Contexto
Este módulo (dentro de `core/strategy.py` y `core/simulator.py`) es la salvaguarda del capital. El bot no opera basándose en "corazonadas", sino en modelos de gestión probabilísticos.

## 🛠 Modelos de Riesgo
1. **Criterio de Kelly Fraccionario:**
    - Calcula el tamaño óptimo de las posiciones basado en el historial real (`trade_history.db`).
    - Fórmula: `f* = (p * b - q) / b` (donde p es winrate y b es RR).
    - Se aplica un multiplicador fraccionario (Kelly Fraction: 0.5) para mayor seguridad.
2. **Value at Risk (VaR):**
    - Calcula el riesgo paramétrico de la cartera basado en los rendimientos diarios.
    - Se usa para alertar de posibles "Flash Crashes" o correcciones de mercado extremas.
3. **Stop-Loss ATR (Dinámico):**
    - Los niveles de salida no son fijos, sino que se ajustan a la volatilidad real del activo.
    - Menor ATR = SL más ajustado. Mayor ATR = SL con mayor "aire" para evitar barridos accidentales.
4. **Multi-Horizon Kill Switches:**
    - Diarios (3%) y Semanales (5%). Si la pérdida de equidad cruza estos umbrales, el bot se suspende para evitar drawdown incontrolado.
5. **Target Volatility Sizing:**
    - Ajusta el tamaño de la posición basado en ATR. En momentos de pánico o gran volatilidad (Current ATR > Ideal ATR), se reduce proporcionalmente el capital arriesgado.

## ⚙️ Reglas de Modificación
- **PROHIBIDO** eliminar la validación del `trade_history.db` antes de calcular a Kelly.
- Los multiplicadores de riesgo (p. ej., TP y SL) deben tener un Ratio Riesgo/Beneficio (RR) mínimo de 1:2.

---
> [!IMPORTANT]
> Nunca sobrepasar el Kelly Total (1.0). El bot está configurado para operar con medio Kelly.
