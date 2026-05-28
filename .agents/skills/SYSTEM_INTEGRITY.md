# 📂 Skill: Integridad del Sistema y Medidas de Seguridad

## 📌 Contexto
Este documento detalla los mecanismos preventivos de seguridad y robustez del código de `TradingProSystem`. Su objetivo es garantizar un funcionamiento ininterrumpido en entornos reales de producción (servicios daemon, despliegues remotos) y mitigar riesgos operacionales.

## 🛡️ Medidas Críticas de Integridad

### 1. Resolución Dinámica de Rutas Absolutas (`pathlib`)
- **Regla:** Queda terminantemente prohibido el uso de strings de rutas relativas simples (ej. `"trade_history.db"`) para archivos críticos.
- **Implementación:** Todos los módulos que requieran acceso a disco deben importar `pathlib` y resolver la raíz del proyecto usando `__file__`:
  ```python
  import pathlib
  _BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
  RUTA_ABSOLUTA = str(_BASE_DIR / "nombre_archivo.ext")
  ```
- **Razón:** Esto asegura que si el bot se levanta como servicio de Windows, tarea programada (`cron`), o se ejecuta desde un directorio arbitrario en la terminal, no se creen archivos fantasmas y se lea siempre la base de datos y modelo correctos.

### 2. Sanitización y Validación de Inputs (Watchlist)
- **Regla:** Todo ticker introducido manualmente por el usuario en el dashboard debe validarse en el frontend antes de su procesamiento.
- **Regex de Validación:** `^[A-Z0-9\.\-]{1,10}$`
- **Implementación (Streamlit / API):**
  ```python
  import re
  def _valid_ticker(t):
      return bool(re.match(r'^[A-Z0-9\.\-]{1,10}$', t.strip().upper()))
  ```
- **Razón:** Previene errores fatales de parseo, peticiones malformadas a `yfinance` o al broker `Alpaca`, e inyecciones de caracteres perjudiciales.

### 3. Versionado Seguro de Modelos ML y Dependencias
- **Regla de Entorno:** Las librerías de serialización (`joblib`), aprendizaje (`scikit-learn`) y cálculo (`numpy`) deben estar estrictamente limitadas por rangos de versión seguros en `requirements.txt`.
- **Límites Establecidos:**
  - `scikit-learn>=1.4.0,<2.0.0`
  - `joblib>=1.3.0,<2.0.0`
  - `numpy>=1.26.0,<2.0.0`
- **Razón:** Previene fallas de des-serialización de bytes (unpickle error) cuando se actualizan paquetes y se intenta cargar un modelo entrenado previamente.

### 4. Protocolo de Reentrenamiento ML y Backups Rotativos
- **Regla:** El script de reentrenamiento nunca debe sobreescribir el modelo activo sin realizar primero un backup y verificar su compatibilidad.
- **Pasos Obligatorios al Entrenar:**
  1. Guardar la versión de scikit-learn (`sklearn.__version__`) y la marca temporal de entrenamiento (`trained_at`) en el diccionario del modelo serializado.
  2. Comprobar si existe un modelo previo en disco y copiarlo a la carpeta `model_backups/` renombrándolo con la estampa temporal del día.
  3. Ejecutar una poda rotativa que mantenga **solamente los 3 backups más recientes**, borrando archivos más antiguos en disco para evitar saturación de almacenamiento.
  4. Mantener la compatibilidad del script de rollback `restore_model.py` en el directorio raíz.

### 5. Monitorización de Subprocesos (Health Server)
- **Regla:** Los subprocesos de larga duración (`bot_worker.py`) deben exponer su estado interno para ser monitorizados desde el frontend.
- **Implementación:** Un servidor FastAPI ligero expone `/health` en el puerto `8001`. El frontend realiza peticiones periódicas para validar latidos (uptime) y el estado general.
- **Razón:** Permite a los usuarios tener visibilidad sobre el demonio de fondo y detectar cuelgues (silent failures) sin tener que revisar manualmente los logs.

### 6. Separación de Entornos (`dev` / `prod`)
- **Regla:** La carga de variables de entorno y secretos debe aislarse según el contexto.
- **Implementación:** `core/brain.py` inyecta `.env.dev` o `.env.prod` dinámicamente utilizando la variable `TRADING_ENV` del sistema (si se omite, carga `.env`).
- **Razón:** Previene operaciones comerciales en cuentas reales por accidente durante ciclos de testeo de nuevas estrategias o calibración de la IA.

### 7. Retención Rotativa de la Base de Datos
- **Regla:** El tamaño del archivo SQLite `trade_history.db` no debe crecer ilimitadamente para mantener el rendimiento.
- **Implementación:** `archive_old_trades(days_to_keep=90)` se invoca cada domingo durante el re-entrenamiento, realiza `DELETE` de registros obsoletos y ejecuta un `VACUUM` en la base de datos para recuperar espacio.
- **Razón:** Previene la degradación en tiempos de consulta del historial analítico y posibles problemas de cuotas de disco tras varios meses de operativa continua.

### 8. Seguridad y Aislamiento del Bot de Telegram
- **Regla:** Queda terminantemente prohibido procesar o responder comandos que provengan de IDs de Telegram no registrados.
- **Implementación:** `core/telegram_listener.py` valida que `chat_id == allowed_chat_id` (cargado desde `.env` como `TELEGRAM_CHAT_ID`) antes de procesar cualquier comando. Los chats no autorizados se registran con una advertencia en los logs del servidor y se ignoran por completo.
- **Razón:** Protege las operaciones comerciales, el capital financiero en Alpaca y los datos sensibles del usuario contra accesos externos no autorizados.

---
> [!WARNING]
> Cualquier cambio que modifique las librerías importadas, el guardado en base de datos o el entrenamiento del modelo de IA debe respetar obligatoriamente estos mecanismos de integridad.
