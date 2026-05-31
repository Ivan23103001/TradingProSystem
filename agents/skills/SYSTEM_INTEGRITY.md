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

### 9. Notificaciones Telegram No Bloqueantes (VPS 24/7)
- **Regla:** `send_message()` en `core/notifier.py` NO debe bloquear el hilo principal de trading. Timeouts de red en la API de Telegram no deben retrasar el loop de escaneo/ejecución.
- **Implementación:** `TelegramNotifier.send_message()` lanza un hilo daemon interno (`threading.Thread(target=self._send_async, daemon=True).start()`) que envía la notificación en background.
- **Razón:** En VPS con micro-cortes de red, un timeout de 10s bloqueando el hilo principal puede causar latencia acumulada de 60s+ por ciclo.

### 10. Firma Criptográfica de Modelos ML (Anti-Pickle Exploit)
- **Regla:** Todo archivo `.pkl` de modelo ML debe ir acompañado de un archivo `.pkl.sig` con firma HMAC-SHA256. Antes de cargar el modelo con `joblib.load()`, se debe ejecutar `_verify_integrity()` para validar que el archivo no ha sido manipulado.
- **Implementación:** `core/ml_engine.py` contiene `_derive_signing_key()` (derivada de machine-id del sistema + PBKDF2-HMAC-SHA256), `_sign_data()` y `_verify_integrity()`. `get_ml_prediction()` rechaza modelos con firma inválida retornando 50 (neutro).
- **Razón:** Mitiga el riesgo de ejecución de código arbitrario por manipulación de archivos pickle en el filesystem del VPS.

### 11. Bloqueo Explícito Dev/Prod en el Broker
- **Regla:** Si `TRADING_ENV=dev`, el sistema debe rechazar tajantemente conexiones con dinero real (`ALPACA_PAPER=false`).
- **Implementación:** `get_broker_client()` en `backend/main.py` verifica: `if env_mode == "dev" and not paper: logging.critical(...); return None`.
- **Razón:** Previene operaciones comerciales accidentales en cuentas reales durante ciclos de desarrollo, testeo o calibración de estrategias.

### 12. Autenticación API Key en Endpoints Sensibles
- **Regla:** El endpoint `POST /api/config` debe requerir autenticación mediante header `X-API-Key`.
- **Implementación:** Middleware HTTP `api_key_auth_middleware` en `backend/main.py` que intercepta requests a `/api/config`. La clave se lee de `bot_config.json` (campo `api_key`) o de la variable de entorno `TRADING_API_KEY`. Requests sin clave o con clave inválida reciben HTTP 401.
- **Razón:** Protege la configuración del bot contra modificaciones no autorizadas si el puerto 8000 queda expuesto en el VPS.

### 13. Validación Obligatoria de Tickers en Todo Punto de Entrada
- **Regla:** Todo ticker debe validarse con regex `^[A-Z0-9\.\-]{1,10}$` en `bot_worker.py`, `backend/main.py` y cualquier UI antes de ser procesado por yfinance o Alpaca.
- **Implementación:** `bot_worker.py` filtra tickers inválidos en la comprensión de lista que construye la watchlist desde `bot_config.json`.
- **Razón:** Previene fallos de parseo, peticiones malformadas a APIs externas, y posibles inyecciones de caracteres desde el archivo de configuración.

---
> [!WARNING]
> Cualquier cambio que modifique las librerías importadas, el guardado en base de datos o el entrenamiento del modelo de IA debe respetar obligatoriamente estos mecanismos de integridad.