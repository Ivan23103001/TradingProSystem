# 📂 Skill: Estructura del Proyecto y Relaciones de Componentes

## 📌 Contexto
Este documento sirve como mapa arquitectónico del proyecto `TradingProSystem`. Es de suma importancia entender cómo interactúan los componentes para evitar romper dependencias al realizar modificaciones.

## 🗺️ Mapa del Directorio del Proyecto
```
TradingProSystem/
│
├── .agents/
│   └── skills/                  # "Memoria" y directrices para agentes de IA
│       ├── ML_INTELLIGENCE_REVOLUTION.md
│       ├── RISK_MANAGEMENT_MASTER.md
│       ├── SMC_TECHNICAL_LOGIC.md
│       ├── SYSTEM_INTEGRITY.md
│       └── PROJECT_STRUCTURE.md
│
├── core/                        # Núcleo del Backend
│   ├── brain.py                 # Cerebro central: constantes, parámetros y riesgo
│   ├── config.py                # Proxy de lectura/escritura de configuraciones
│   ├── database.py              # Acceso seguro SQLite en modo WAL y concurrente
│   ├── ml_engine.py             # Ensamble de predicción (RF + GB) y backups
│   ├── strategy.py              # Lógica SMC, indicadores y generación de señales
│   └── telegram_listener.py     # Escuchador interactivo en tiempo real de Telegram (24/7)
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
├── bot_worker.py                # Hilo principal de ejecución de trading (24/7)
├── restore_model.py             # Herramienta de Rollback del modelo ML
├── requirements.txt             # Dependencias del proyecto fijadas
└── bot_config.json              # Configuración persistente del usuario en tiempo de ejecución
```

## 🛠️ Roles de los Componentes y Flujos de Datos

### 1. El Cerebro Central (`core/brain.py`)
- **Rol:** Centraliza todas las variables de riesgo, multiplicadores SMC, y umbrales globales.
- **Acceso:** Todas las clases de lógica técnica o visual leen de aquí en lugar de usar valores hardcoded.
- **Paths Absolutos:** Define el directorio raíz del proyecto (`_BASE_DIR`) dinámicamente y expone rutas absolutas para la base de datos, el archivo de configuración y el modelo de ML, garantizando un inicio seguro como servicio daemon.

### 2. Gestión de Datos (`core/database.py`)
- **Rol:** Centraliza el acceso a SQLite. Habilita el modo WAL (Write-Ahead Logging) y timeouts elevados (15s) para permitir lecturas y escrituras seguras concurrentes.
- **Flujo:** 
  - `bot_worker.py` escribe## 🎨 Frontend UI (Reflex Web App)
- `trading_pro_ui/`: Aplicación frontend principal.
  - `trading_pro_ui.py`: El cerebro y estado de la interfaz gráfica web en Reflex. Define el `rx.State` para vincular datos de Pandas/SQLite al frontend web y los componentes de UI.
- `rxconfig.py`: Configuración del servidor y app Reflex.
- `scripts/app_streamlit_backup.py`: [DEPRECADO] Interfaz antigua de Streamlit en caso de necesitar validaciones en frío.kit-learn` y maneja una carpeta rotativa de copias de seguridad de modelos anteriores.

### 4. Lógica de Trading (`core/strategy.py`)
- **Rol:** Detecta patrones SMC (Order Blocks, Liquidity Sweeps, Imbalances) y calcula las señales de trading combinando indicadores tradicionales y la inferencia de `core/ml_engine.py`.

### 5. Frontend UI (`app.py`)
- **Rol:** Dashboard interactivo para ver balances, gráficos interactivos con Plotly, logs, y ajustar parámetros en tiempo de ejecución de manera visual.

### 6. Ejecución en Producción (`bot_worker.py`)
- **Rol:** Script daemon en segundo plano que corre indefinidamente. Realiza descargas con yfinance, calcula señales con `strategy.py`, efectúa ejecuciones en Alpaca de forma asíncrona, guarda registros en base de datos e inicia el escuchador de Telegram en segundo plano.

### 7. Escuchador de Telegram (`core/telegram_listener.py`)
- **Rol:** Servidor interactivo en segundo plano (hilo daemon) que realiza sondeos a Telegram (`getUpdates`). Responde a comandos del usuario en tiempo real (`/estado`, `/balance`, `/historial_hoy`) con un estricto filtro de seguridad que bloquea cualquier ID no autorizado.

---
> [!NOTE]
> Al agregar o cambiar cualquier característica, debes identificar a qué componente pertenece y verificar que sus puertos de entrada/salida (parámetros y llamadas) se sincronicen de acuerdo al [Protocolo de Sincronización](file:///.agents/skills/SYNC_PROTOCOL.md).
