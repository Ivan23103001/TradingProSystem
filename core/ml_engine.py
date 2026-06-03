import pandas as pd
import numpy as np
import pathlib
import sklearn
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
import joblib
import os
import logging
import hashlib
import hmac
import threading

# Directorio raíz del proyecto (resuelto desde la ubicación de este archivo)
_BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()
MODEL_PATH = str(_BASE_DIR / "ml_trading_model.pkl")
MODEL_SIG_PATH = MODEL_PATH + ".sig"
MODEL_BACKUPS_DIR = _BASE_DIR / "model_backups"

# Clave de firma HMAC para integridad del modelo (anti-manipulación pickle)
# Derivada de machine-id si existe, más un secreto fijo como fallback
def _derive_signing_key():
    key = b"TradingProSystem_v5_ML_Model_Signing_Key_2026"
    try:
        # Intentar derivar de /etc/machine-id (Linux) o registry (Windows)
        if os.name == "posix" and os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "rb") as f:
                machine_id = f.read().strip()
            key = hashlib.pbkdf2_hmac("sha256", key, machine_id, 10000)
        elif os.name == "nt":
            import subprocess
            try:
                result = subprocess.run(
                    ["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"],
                    capture_output=True, text=True
                )
                if result.returncode == 0 and "MachineGuid" in result.stdout:
                    guid = result.stdout.split("REG_SZ")[-1].strip().encode()
                    key = hashlib.pbkdf2_hmac("sha256", key, guid, 10000)
            except Exception:
                pass
    except Exception:
        pass
    return key

_SIGNING_KEY = _derive_signing_key()

def _sign_data(data: bytes) -> str:
    """Genera firma HMAC-SHA256 de los datos serializados."""
    return hmac.new(_SIGNING_KEY, data, hashlib.sha256).hexdigest()

# Flag global para evitar spam de logs de firma (máximo un mensaje por sesión)
_warned_missing_sig = False
_confirmado_firma_ok = False

# --- Caché en memoria del modelo ML (evita I/O en cada predicción) ---
# El modelo y sus componentes solo se cargan UNA VEZ por sesión del proceso.
# Se invalida automáticamente tras reentrenamiento (train_trading_model).
_cached_model = None
_cache_lock = threading.Lock()


def invalidate_model_cache():
    """
    Invalida el caché del modelo ML para forzar una recarga en la siguiente predicción.
    Llamado por train_trading_model() tras guardar un nuevo modelo en disco.
    Thread-safe: adquiere el lock antes de modificar _cached_model.
    """
    global _cached_model
    with _cache_lock:
        _cached_model = None
    logging.info("🔄 Caché de modelo ML invalidado — se recargará en la próxima predicción.")


def _load_model_into_cache():
    """
    Carga y verifica el modelo ML una sola vez, guardándolo en _cached_model.
    Retorna el dict del modelo o None si la carga/verificación falla.
    Usa Double-Checked Locking para evitar que múltiples hilos carguen
    simultáneamente el modelo desde disco durante el primer ciclo de escaneo.
    """
    global _cached_model

    # Primer check sin lock (fast path para el 99.9% de las llamadas)
    if _cached_model is not None:
        return _cached_model

    # Segundo check con lock (solo el primer hilo que llega carga el modelo)
    with _cache_lock:
        if _cached_model is not None:
            return _cached_model

        if not os.path.exists(MODEL_PATH):
            logging.warning("Modelo ML no encontrado en disco.")
            return None

        if not _verify_integrity(MODEL_PATH):
            logging.error("[!] Modelo ML rechazado por fallo de integridad (firma HMAC inválida).")
            return None

        try:
            _cached_model = joblib.load(MODEL_PATH)
            logging.info(f"✅ Modelo ML cargado en memoria (features: {len(_cached_model.get('features', []))})")

            # Verificar coincidencia de versión de sklearn (solo se emite en la carga inicial)
            if isinstance(_cached_model, dict):
                saved_ver = _cached_model.get('sklearn_version', 'unknown')
                if saved_ver != 'unknown' and saved_ver != sklearn.__version__:
                    logging.warning(
                        f"[!] Modelo ML entrenado con sklearn {saved_ver}, "
                        f"pero la versión actual es {sklearn.__version__}"
                    )

            return _cached_model
        except Exception as e:
            logging.error(f"Error cargando modelo ML: {e}")
            return None


def _verify_integrity(model_path=None):
    """
    Verifica que el archivo .pkl no haya sido manipulado usando su firma HMAC.
    - Si el .sig no existe, intenta generarlo y emite un solo INFO de confirmación.
    - Si el .sig existe y es válido, NO emite nada (silencio total).
    - Solo emite ERROR si hay manipulación detectada (firma inválida).
    """
    global _warned_missing_sig, _confirmado_firma_ok
    pkl_path = model_path or MODEL_PATH
    sig_path = pkl_path + ".sig"

    if not os.path.exists(pkl_path):
        return False

    if not os.path.exists(sig_path):
        # Modelo sin firma — RECHAZAR. La firma debe generarse explícitamente
        # durante el entrenamiento, no automáticamente en verificación.
        logging.error(f"[!] Firma HMAC no encontrada para {pkl_path} — el modelo debe ser re-entrenado para generar su firma.")
        return False

    # Firma existe — validar en silencio
    with open(pkl_path, "rb") as f:
        raw = f.read()
    with open(sig_path, "r") as f:
        expected_sig = f.read().strip()
    computed_sig = _sign_data(raw)
    if not hmac.compare_digest(computed_sig, expected_sig):
        logging.error(f"[!] FIRMA INVALIDA para {pkl_path} — posible manipulación del modelo pickle.")
        return False
    return True

def prepare_features(df, bars_forward=3, min_move_pct=0.015):
    """
    Convierte TODOS los indicadores técnicos disponibles en features para el modelo.
    Versión 4.2: Incluye Microestructura Institucional (OB & Sweeps) y targets dinámicos.
    """
    try:
        if df is None or len(df) < 50:
            return pd.DataFrame(), pd.Series(), []
            
        data = df.copy()
        
        # Features básicos
        base_features = ['RSI', 'Stoch_K', 'MACD_Hist', 'MACD']
        
        # Features avanzados (institucionales)
        advanced_features = ['ADX', 'ROC', 'ATR', 'Sharpe_Ratio', 'Beta', 'Std_Dev', 'Z_Score', 
                             'Bearish_Sweep_Signal', 'Bullish_Sweep_Signal', 'Bullish_OB', 'Bearish_OB',
                             'FVG_Bullish', 'FVG_Bearish']
        
        # Features de volumen
        volume_features = ['MFI', 'CMF']
        
        features = []
        for f in base_features + advanced_features + volume_features:
            if f in data.columns:
                features.append(f)
        
        if len(features) < 4:
            return pd.DataFrame(), pd.Series(), []
            
        # Features derivados
        if 'Bullish_OB' in data.columns:
            # Distancia al OB más reciente distinto de cero
            data['Dist_BullOB'] = (data['Close'] - data['Bullish_OB']) / (data['Close'] + 1e-9)
            features.append('Dist_BullOB')
        if 'Bearish_OB' in data.columns:
            data['Dist_BearOB'] = (data['Close'] - data['Bearish_OB']) / (data['Close'] + 1e-9)
            features.append('Dist_BearOB')
            
        if 'POC' in data.columns:
            data['Dist_POC'] = (data['Close'] - data['POC']) / (data['POC'] + 1e-9)
            features.append('Dist_POC')
        if 'EMA_20' in data.columns:
            data['Dist_EMA20'] = (data['Close'] - data['EMA_20']) / (data['EMA_20'] + 1e-9)
            features.append('Dist_EMA20')
        if 'EMA_200' in data.columns:
            data['Dist_EMA200'] = (data['Close'] - data['EMA_200']) / (data['EMA_200'] + 1e-9)
            features.append('Dist_EMA200')
        
        data['Return_1d'] = data['Close'].pct_change()
        data['Return_5d'] = data['Close'].pct_change(5)
        features += ['Return_1d', 'Return_5d']
        
        # Target: Clean move — sube ≥ min_move_pct en bars_forward barras sin caer > (min_move_pct / 2) en el camino
        # v5.1: forward_min mira hacia adelante (sin doble shift que perdía 2*bars_forward filas)
        forward_low = data['Low'].iloc[::-1].rolling(bars_forward + 1).min().iloc[::-1]
        forward_low.index = data.index
        data['Target'] = (
            (data['Close'].shift(-bars_forward) > data['Close'] * (1.0 + min_move_pct)) &
            (forward_low > data['Close'] * (1.0 - min_move_pct / 2.0))
        ).astype(int)
        data = data.dropna(subset=features + ['Target'])
        
        if data.empty or len(data) < 50:
            return pd.DataFrame(), pd.Series(), []
            
        return data[features], data['Target'], features
    except Exception:
        return pd.DataFrame(), pd.Series(), []

def train_trading_model(df, n_estimators=150, max_depth=12, bars_forward=3, min_move_pct=0.015):
    try:
        if len(df) < 100:
            return None, "Datos insuficientes"
        X, y, feature_names = prepare_features(df, bars_forward=bars_forward, min_move_pct=min_move_pct)
        if len(X) < 50:
            return None, "Datos válidos insuficientes"
            
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # Robust Scaler para manejar outliers en datos de mercado de forma segura y robusta
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Modelo 1: Random Forest
        rf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, min_samples_leaf=10, random_state=42, n_jobs=-1)
        rf.fit(X_train_scaled, y_train)
        
        # Modelo 2: Gradient Boosting (Excelente para secuencias y relaciones no lineales de tendencia)
        gb = GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.05, random_state=42)
        gb.fit(X_train_scaled, y_train)
        
        # Evaluamos precisión del Ensamble
        rf_preds = rf.predict_proba(X_test_scaled)[:, 1]
        gb_preds = gb.predict_proba(X_test_scaled)[:, 1]
        ensemble_preds = (rf_preds + gb_preds) / 2
        ensemble_binary = (ensemble_preds >= 0.5).astype(int)
        
        from sklearn.metrics import accuracy_score
        accuracy = accuracy_score(y_test, ensemble_binary)
        
        # Backup del modelo anterior (si existe) antes de sobreescribir
        if os.path.exists(MODEL_PATH):
            import shutil
            from datetime import datetime
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                MODEL_BACKUPS_DIR.mkdir(exist_ok=True)
                backup_path = MODEL_BACKUPS_DIR / f"ml_model_{ts}.pkl"
                shutil.copy2(MODEL_PATH, backup_path)
                
                # Limpiar backups antiguos (mantener solo los 3 más recientes)
                backups = sorted(MODEL_BACKUPS_DIR.glob("ml_model_*.pkl"), key=os.path.getmtime, reverse=True)
                for old in backups[3:]:
                    try:
                        old.unlink()
                        logging.info(f"[-] Backup antiguo eliminado: {old.name}")
                    except Exception as ex:
                        logging.error(f"Error al eliminar backup antiguo {old}: {ex}")
            except Exception as e:
                logging.error(f"Error al realizar backup del modelo ML: {e}")

        # Guardamos el bundle completo con el Scaler para evitar sesgos en inferencia
        joblib.dump({
            'rf_model': rf,
            'gb_model': gb,
            'scaler': scaler,
            'features': feature_names,
            'accuracy': accuracy,
            'sklearn_version': sklearn.__version__,
            'trained_at': pd.Timestamp.now().isoformat()
        }, MODEL_PATH)
        
        # Firmar el modelo para detectar manipulaciones (anti-pickle exploit)
        with open(MODEL_PATH, "rb") as f:
            raw_model = f.read()
        signature = _sign_data(raw_model)
        with open(MODEL_SIG_PATH, "w") as f:
            f.write(signature)
        logging.info(f"🔐 Modelo ML firmado (HMAC-SHA256) → {MODEL_SIG_PATH}")

        # Invalidar caché en memoria para que la siguiente predicción use el nuevo modelo
        invalidate_model_cache()
        
        return accuracy, f"Entrenamiento exitoso (Accuracy Ensamble: {accuracy:.1%}, Features: {len(feature_names)})"
    except Exception as e:
        return None, str(e)

def get_ml_prediction(df):
    """
    Predicción del modelo ML usando caché en memoria.
    El modelo se carga de disco solo UNA VEZ por sesión del proceso.
    """
    try:
        # Usar el caché en memoria (carga + verificación HMAC solo en la primera llamada)
        saved = _load_model_into_cache()
        if saved is None:
            return 50
        
        # Soporte para retrocompatibilidad con el modelo anterior (legacy sin ensamble)
        if isinstance(saved, dict) and 'rf_model' not in saved:
            model = saved.get('model')
            if model is None:
                logging.error("[!] Modelo legacy sin clave 'model' ni 'rf_model' — corrupto.")
                return 50
            expected_features = saved.get('features', None)
            X, _, actual_features = prepare_features(df)
            if X.empty: return 50
            if expected_features and set(expected_features) != set(actual_features):
                 return 50
            last_row = X.iloc[[-1]]
            # Legacy: modelo simple sin scaler
            if hasattr(model, 'predict_proba'):
                probs = model.predict_proba(last_row)[0]
                classes = model.classes_.tolist()
                if 1 in classes: return int(probs[classes.index(1)] * 100)
            return 50
            
        # Inferencia con el nuevo Ensamble robusto (RF + GB) — desde caché
        rf_model = saved['rf_model']
        gb_model = saved['gb_model']
        scaler = saved['scaler']
        expected_features = saved['features']
        
        X, _, actual_features = prepare_features(df)
        if X.empty: return 50
        if expected_features and set(expected_features) != set(actual_features):
             return 50
             
        last_row = X.iloc[[-1]]
        last_row_scaled = scaler.transform(last_row)
        
        # Obtener probabilidades estimadas de ambos clasificadores
        rf_probs = rf_model.predict_proba(last_row_scaled)[0]
        gb_probs = gb_model.predict_proba(last_row_scaled)[0]
        
        rf_classes = rf_model.classes_.tolist()
        gb_classes = gb_model.classes_.tolist()
        
        rf_p1 = rf_probs[rf_classes.index(1)] if 1 in rf_classes else 0.5
        gb_p1 = gb_probs[gb_classes.index(1)] if 1 in gb_classes else 0.5
        
        # Promedio del ensamble adaptativo
        ensemble_prob = (rf_p1 + gb_p1) / 2
        return int(ensemble_prob * 100)
    except Exception:
        return 50


def calculate_ml_rolling_accuracy(db_path="trade_history.db", limit=15):
    """
    Calcula la precisión real del modelo ML basándose en los resultados reales de los trades cerrados.
    Retorna la precisión rodante (0.0 a 1.0) y el peso dinámico aconsejado para el ensamble.
    """
    from core.database import get_connection
    if not os.path.exists(db_path):
        return 0.50, 0.40  # Neutro, Peso estándar

    try:
        conn = get_connection(db_path)
        # Traer trades cerrados donde la IA tuvo voto decisivo (score distinto a 50)
        df_trades = pd.read_sql_query(
            "SELECT pnl, score, tipo FROM trades WHERE pnl IS NOT NULL AND score != 50 ORDER BY id DESC LIMIT ?",
            conn, params=(limit,)
        )
        # No cerrar: la conexión pertenece al pool thread-local

        if df_trades.empty or len(df_trades) < 5:
            return 0.50, 0.40

        # Un trade es "correcto" si dio ganancia (pnl > 0)
        correct = df_trades[df_trades['pnl'] > 0]
        accuracy = len(correct) / len(df_trades)

        # Ajuste dinámico del peso del modelo (Auto-Adaptación del Cerebro)
        if accuracy >= 0.65:
            weight = 0.55
        elif accuracy >= 0.50:
            weight = 0.40
        else:
            weight = 0.15

        return accuracy, weight
    except Exception:
        return 0.50, 0.40
