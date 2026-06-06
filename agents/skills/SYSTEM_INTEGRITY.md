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

### 14. Bloqueo de Archivos Sensibles en Nginx (v5.1)
- **Regla:** Nginx NO debe servir archivos sensibles del proyecto bajo ninguna circunstancia. El bloque `location /` con `try_files` puede exponer accidentalmente `.env`, `.db`, `.git`, `*.py`, y `*.pkl`.
- **Implementación:** Añadir bloques `location` con `deny all` antes del fallback SPA:
  ```nginx
  location ~ /\.(?!well-known) { deny all; return 404; }
  location ~ \.(db|db-shm|db-wal|pkl|py|pyc|log)$ { deny all; return 404; }
  location ~ /\.git { deny all; return 404; }
  ```
- **Verificación:** `curl http://localhost/.env` debe retornar 404, no el contenido del archivo.
- **Razón:** Previene la fuga de API keys de Alpaca, tokens de Telegram, base de datos de trades y código fuente ante accesos no autorizados.

### 15. Defensive Null Checks en el Frontend React (v5.1)
- **Regla:** Todo acceso a propiedades de objetos provenientes de la API debe usar optional chaining (`?.`) y nullish coalescing (`??`) para evitar crashes por `undefined`.
- **Implementación:** En `Dashboard.tsx`, 5 puntos críticos usan el patrón `(value?.startsWith("+") ?? false)`:
  - `data.change` (KPIs de precio)
  - `item.change` (Market Map)
  - `pos.pnl` (Portfolio)
  - `pos.pnl_pct` (Portfolio)
  - `trade.pnl` (Trade History)
- **Razón:** Si la API responde con un campo faltante o `undefined`, el componente no crashea con `Cannot read properties of undefined (reading 'startsWith')` y en su lugar usa el fallback `false`.

### 16. Clonación Idempotente de Rutas /api/v1 (v5.1)
- **Regla:** La clonación de rutas `/api/*` → `/api/v1/*` en `backend/main.py` debe ser idempotente para evitar la duplicación infinita `/api/v1/api/v1/api/v1/...` que ocurre cuando el módulo se recarga (PM2 restart, Uvicorn --reload).
- **Implementación:** Doble guard en el loop de clonación:
  ```python
  if _path.startswith("/api/") and "/api/v1" not in _path:
      _v1_path = _path.replace("/api/", "/api/v1/", 1)
      if not any(r.path == _v1_path for r in _v1_router.routes):
          _v1_router.add_api_route(...)
  ```
- **Razón:** El guard anterior `not _path.startswith("/api/v1")` fallaba porque el estado de `app.router.routes` persiste entre recargas, causando que rutas ya clonadas se clonaran de nuevo con prefijo adicional.

### 17. Rate Limiting en Nginx (v5.1)
- **Regla:** Nginx debe limitar la tasa de requests para proteger el backend contra sobrecarga (DDoS básico o bugs que generen bucles de peticiones).
- **Implementación recomendada:**
  ```nginx
  limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
  limit_req zone=api_limit burst=20 nodelay;
  ```
- **Razón:** Uvicorn con 1 worker puede saturarse con requests simultáneos. El rate limiting en Nginx absorbe el impacto antes de que llegue al backend.

### 18. HTTPS/TLS Obligatorio en Producción (v5.3)
- **Regla:** Todo el tráfico de producción debe ir cifrado con TLS 1.2/1.3. Jamás exponer credenciales de Alpaca o API Keys sobre HTTP sin cifrar.
- **Implementación:** Nginx configurado con certificados Let's Encrypt vía DuckDNS (`tps-system.duckdns.org`). Redirección 301 de HTTP a HTTPS. HSTS con `max-age=31536000`. Headers de seguridad: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Permissions-Policy`, `CSP`.
- **Verificación:** `curl -I https://tps-system.duckdns.org/api/health` debe retornar `HTTP/2 200` y `strict-transport-security`.
- **Razón:** Sin TLS, cualquier atacante en la misma red puede interceptar credenciales de Alpaca y API Keys vía MITM.

### 19. Consultas SQL Parametrizadas (v5.3)
- **Regla:** Queda terminantemente prohibido el uso de f-strings para interpolar variables en consultas SQL. Usar siempre placeholders `?` con tuplas de parámetros.
- **Implementación:** `core/database.py` — todas las funciones (`get_trade_history`, `get_equity_history`, `archive_old_trades`, `get_audit_logs`) usan `params=(limit,)` en lugar de f-strings.
- **Razón:** Defensa en profundidad contra inyección SQL. Aunque los valores actuales son internos, la práctica previene vulnerabilidades futuras.

### 20. HMAC Signing Key Configurable vía Entorno (v5.3)
- **Regla:** La clave de firma HMAC para modelos pickle no debe estar hardcodeada en el código fuente. Debe ser configurable vía variable de entorno.
- **Implementación:** `core/ml_engine.py` — `_derive_signing_key()` lee `ML_SIGNING_SECRET` del entorno. Si no existe, usa fallback derivado de machine-id. `.env.example` documenta la variable.
- **Razón:** Si el código fuente se expone (repositorio público, backup), la clave hardcodeada permitiría a un atacante generar firmas válidas para modelos maliciosos.

### 21. Telegram parse_mode HTML para Comandos (v5.3)
- **Regla:** El listener de Telegram debe usar `parse_mode: "HTML"` para respuestas de comandos. `MarkdownV2` es demasiado estricto y rechaza mensajes con caracteres especiales sin escapar.
- **Implementación:** `core/telegram_listener.py` — `send_reply()` usa `parse_mode: "HTML"`. Formateo con `<b>`, `<code>`, `<i>`. El notifier (`core/notifier.py`) mantiene `MarkdownV2` para mensajes simples de alertas.
- **Razón:** MarkdownV2 rechaza silenciosamente mensajes con `*`, `_`, `(`, `)`, `.` sin escapar. Los comandos contienen precios (`$598.34`), porcentajes (`+1.2%`), y tickers con puntos — todos rompen MarkdownV2.

### 22. Reutilización de ThreadPoolExecutor en bot_worker.py (v5.3)
- **Regla:** El `ThreadPoolExecutor` para escaneo paralelo de tickers debe crearse UNA sola vez y reutilizarse en todos los ciclos. No crear/destruir uno nuevo cada ~60s.
- **Implementación:** `bot_worker.py` — el executor se crea antes del `while True` y se destruye en un bloque `finally` al salir del loop. `ticker_executor.shutdown(wait=True)` garantiza limpieza.
- **Razón:** Crear/destruir 10 hilos cada 60s genera ~600 operaciones de creación/destrucción por hora, desperdiciando recursos del VPS.

### 23. Protección Contra Entradas Duplicadas en Alpaca (IMP-0, v5.3)
- **Regla:** El worker NUNCA debe intentar ejecutar una orden sobre un ticker que ya tiene una posición abierta en Alpaca. Verificar `active_positions` antes de cualquier `execute_trade()`.
- **Implementación:** `bot_worker.py` — chequeo `IMP-0` que verifica `t in active_symbols` derivado de `state_memory["active_positions"]`. Si el ticker ya está abierto, hace `continue` inmediato.
- **Razón:** Sin este chequeo, Alpaca rechaza con `40310000 "insufficient qty available"`, generando 3 reintentos con backoff (~10s de delay), ruido en logs, y flag `degraded` activado innecesariamente.

### 24. SL/TP con Valores Extremos en Reconstrucción de Posiciones (v5.3)
- **Regla:** Al reconstruir `software_monitored` desde posiciones abiertas en Alpaca tras un reinicio, los valores iniciales de SL/TP deben ser extremos (`-1e9` / `1e9`) para evitar disparos falsos en el primer ciclo.
- **Implementación:** `bot_worker.py` — `sl_price: -1e9 if side == 'buy' else 1e9`, `tp_price: 1e9 if side == 'buy' else -1e9`. Se recalculan con datos reales en el siguiente ciclo.
- **Razón:** Con `sl_price: 0.0` y `tp_price: 0.0`, el monitor software disparaba inmediatamente TAKE PROFIT (porque `current_price >= 0.0` siempre es True), causando errores `40310000` en Alpaca.

### 25. Type Hints PEP 484 en Funciones Core (v5.3)
- **Regla:** Las funciones core de `database.py`, `strategy.py` y `data_fetcher.py` deben incluir type hints para mejorar la mantenibilidad y detección temprana de errores.
- **Implementación:** `save_trade(ticker: str, tipo: str, ...) -> None`, `apply_strategy(df: pd.DataFrame, ...) -> pd.DataFrame`, `get_stock_data(ticker: str, ...) -> pd.DataFrame`, etc.
- **Razón:** Facilita la verificación estática con mypy/pyright, documenta las interfaces, y previene errores silenciosos por tipos incorrectos.

### 26. Backend Lazy Init Modular (v5.3)
- **Regla:** La inicialización de los 7 módulos core del backend debe estar en un módulo independiente (`backend/init_modules.py`), no inline en `main.py`.
- **Implementación:** `backend/init_modules.py` expone `init_all_modules(base_dir)` que retorna un dict estructurado con `ok`, `errors`, `modules`. `main.py` solo asigna los resultados a variables globales.
- **Razón:** Reduce `main.py` en ~100 líneas, permite testear la inicialización de forma aislada, y devuelve un resultado estructurado en vez de modificar variables globales directamente.

### 27. Tabla price_alerts para Alertas de Precio (v5.3)
- **Regla:** Las alertas de precio configuradas desde Telegram deben persistir en SQLite, no en memoria volátil.
- **Implementación:** Nueva tabla `price_alerts` con columnas: `id`, `ticker`, `target_price`, `direction` (CHECK ABOVE/BELOW), `active`, `created_at`. CRUD completo: `save_price_alert()`, `get_price_alerts()`, `delete_price_alert()` (soft delete). Índice `idx_alerts_active`.
- **Razón:** Las alertas deben sobrevivir reinicios del worker. El soft delete permite auditoría sin perder datos.

### 28. matplotlib con Backend Agg para Gráficos en VPS (v5.3)
- **Regla:** Al generar gráficos en un VPS sin display, usar `matplotlib.use('Agg')` antes de importar `pyplot`. No generar archivos temporales en disco — usar `BytesIO` en memoria.
- **Implementación:** `core/telegram_listener.py` — `_cmd_chart()` configura `matplotlib.use('Agg')`, dibuja velas japonesas con `patches.Rectangle`, guarda en `BytesIO`, envía vía `sendPhoto`, y cierra el buffer.
- **Razón:** Sin backend Agg, matplotlib intenta abrir una ventana gráfica y crashea en entornos headless. `BytesIO` evita archivos basura en el filesystem del VPS.

---
> [!WARNING]
> Cualquier cambio que modifique las librerías importadas, el guardado en base de datos o el entrenamiento del modelo de IA debe respetar obligatoriamente estos mecanismos de integridad.
