================================================================================
   TRADING PRO SYSTEM - Terminal Cuantitativa Multisectorial
   Versión: 2.5.0 (Fractional & Multi-Directional Update)
   Última actualización: 13 de Marzo de 2026
================================================================================


================================================================================
1. DESCRIPCIÓN GENERAL DEL PROYECTO
================================================================================

   TradingProSystem es un ecosistema de trading algorítmico de alto nivel, 
   diseñado con una estética de terminal institucional profesional.
   Utiliza un Motor de Inserción Matemática con Inteligencia Artificial para
   detectar oportunidades de alta probabilidad tanto a la ALZA como a la BAJA.

   Novedad Clave: Soporte para inversiones por MONTOS FIJOS (Fractional Shares),
   permitiendo operar con capitales pequeños ($1 - $1,000 USD) de forma eficiente.


================================================================================
2. META Y OBJETIVOS DEL PROYECTO
================================================================================

   META PRINCIPAL:
   Desplegar una plataforma de trading autónoma que gestione riesgo mediante
   montos fijos en dólares y ejecute estrategias de confluencia técnica + IA.

   OBJETIVOS COMPLETADOS:
   [x] Fase 1: Motor de datos Multitickers (Yahoo Finance).
   [x] Fase 2: Estrategia de Confluencia (RSI, MACD, Bollinger, EMAs).
   [x] Fase 3: Interfaz Sidebar-Focused (Optimización de espacio).
   [x] Fase 4: Integración de Machine Learning (Predicción de Probabilidad).
   [x] Fase 5: Soporte para Órdenes Fraccionarias (Inversión por monto en USD).
   [x] Fase 6: Estrategia Bidireccional (Long / Short Selling).
   [x] Fase 7: Sistema de Alertas vía Telegram.
   [x] Fase 8: Conector con Alpaca Markets (Paper/Live Trading).


================================================================================
3. ESTRUCTURA PROFESIONAL DE ARCHIVOS
================================================================================

    TradingProSystem/
    |
    |-- core/               -> (Back-end: El cerebro del bot)
    |   |-- data_fetcher.py -> Motor de descarga intradía y diaria.
    |   |-- strategy.py     -> Motor de puntuación (Sistema de Score 0-100).
    |   |-- ml_engine.py    -> Motor de IA (Random Forest + Scikit-Learn).
    |   |-- broker.py       -> Cliente Alpaca (Soporta Qty y Notional).
    |   |-- simulator.py    -> Laboratorio de Backtesting.
    |   |-- notifier.py     -> Enrutador de notificaciones a Telegram.
    |
    |-- ui/                 -> (Front-end: La cara de la terminal)
    |   |-- styles.py       -> CSS Institucional Bloomberg-Style.
    |
    |-- app.py              -> Orquestador Principal (Streamlit Interface).
    |-- trade_history.db    -> Registro permanente de operaciones (SQLite).
    |-- requirements.txt    -> Ecosistema de dependencias.


================================================================================
4. FUNCIONALIDADES DESTACADAS
================================================================================

   --- GESTIÓN DE RIESGO POR MONTO (NUEVO) ---
   - Puedes elegir exactamente cuántos dólares arriesgar por operación.
   - El bot calcula automáticamente cuántas fracciones de acción comprar o vender.
   - Ideal para cuentas pequeñas ($100 - $1,000 MXN).

   --- TRADING BIDIRECCIONAL (ALZA Y BAJA) ---
   - Compras (Long): Score >= 85. Ganancia si el precio sube.
   - Ventas en Corto (Short): Score <= 15. Ganancia si el precio baja.

   --- LAYOUT OPTIMIZADO ---
   - Sidebar Nativo: Todo el control a la izquierda para dejar espacio al gráfico.
   - Ticker Cards: Visualización rápida de precios y variaciones porcentuales.
   - Gráfico de 3 Paneles: Velas/Bollinger, Volumen y RSI sincronizados.


================================================================================
5. LO QUE VIENE (ROADMAP / MEJORAS FUTURAS)
================================================================================

   CORTO PLAZO (1-2 semanas):
   [ ] Tablero Visual de P&L: Gráfico de balance total vs tiempo.
   [ ] Órdenes de Protección: Stop Loss y Take Profit configurables desde la UI.
   [ ] Filtro de Mercado: Evitar operar si el índice general (SPY) está muy bajista.

   MEDIANO PLAZO (1-3 meses):
   [ ] Análisis de Sentimiento: Integración con noticias de IA (Grok/GPT/NewsAPI).
   [ ] Scanner de Mercado Total: Escanear todas las acciones del S&P500 automáticamente.
   [ ] Optimización en la Nube: Configuración de PM2 para persistencia total.


================================================================================
6. COMANDOS ÚTILES
================================================================================

   # Instalar dependencias:
   pip install -r requirements.txt

   # Iniciar la terminal:
   python -m streamlit run app.py

   # Ver historial de trades:
   (Pestaña "Mi Historial" en la aplicación)


================================================================================
7. ADVERTENCIA LEGAL
================================================================================

   ADVERTENCIA: El trading conlleva riesgos. Este sistema es una herramienta 
   de análisis estadístico, NO una garantía de éxito. Nunca inviertas dinero 
   que no estés dispuesto a perder. Las operaciones en corto (Short) tienen
   un riesgo elevado.
================================================================================
