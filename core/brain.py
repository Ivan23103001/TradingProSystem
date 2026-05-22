import os
import json
import sqlite3
import pathlib
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Directorio raíz del proyecto (resuelto desde la ubicación de este archivo)
# Funciona sin importar desde qué directorio se ejecute el proceso
_BASE_DIR = pathlib.Path(__file__).parent.parent.resolve()

# --- CONFIGURACIÓN BASE ---
# Rutas absolutas → el bot funciona desde cualquier directorio (servicio Windows, cron, etc.)
CONFIG_FILE = str(_BASE_DIR / "bot_config.json")
MODEL_FILE = str(_BASE_DIR / "ml_trading_model.pkl")
DB_FILE = str(_BASE_DIR / "trade_history.db")

class TradingBrain:
    """
    EL CEREBRO CENTRAL (Brain Engine v1.0)
    Garantiza que toda la información del bot esté sincronizada, validada y actualizada.
    """
    
    # --- CONSTANTES TÉCNICAS (SMC & RISK) ---
    # Centralizamos toda la "inteligencia" técnica aquí.
    SMC_THRESHOLD_ATR = 1.5           # Multiplicador ATR para Order Blocks
    SMC_WICK_RATIO = 0.6              # Ratio de mecha para Liquidity Sweeps
    SMC_LOOKBACK = 20                 # Ventana de búsqueda de stops
    SMC_BREAKER_MULT = 1.2            # Multiplicador de volumen para Breakers
    SMC_VOLUME_MULT = 1.8             # Multiplicador de volumen para detectar Imbalances institucionales

    
    RISK_KELLY_FRACTION = 0.5         # Fracción de Kelly (Conservador)
    RISK_MIN_RR = 2.0                 # Ratio Riesgo/Beneficio mínimo
    RISK_VAR_CONFIDENCE = 0.95        # Nivel de confianza para VaR

    MAX_CONCURRENT_POSITIONS = 5      # Límite de posiciones abiertas simultáneas
    DAILY_MAX_LOSS_PCT = 0.03         # Circuit breaker: pérdida máxima diaria (3%)
    WEEKLY_MAX_LOSS_PCT = 0.05        # Cuarentena: pérdida máxima semanal (5%)
    MINIMUM_TRADE_USD = 50            # Mínimo absoluto por operación
    MAX_POSITION_EQUITY_PCT = 0.25    # Máximo 25% del buying power por posición
    ATR_BASE_PERCENT = 0.02           # ATR base ideal (2% del precio) para calcular Target Volatility Sizing


    # VIX < 15 → umbral 60, VIX < 22 → umbral 65, VIX >= 22 → umbral 75
    VIX_SCORE_THRESHOLDS = [(15, 60), (22, 65), (99, 75)]

    # --- DIRECTION CONTROL ---
    DIRECTION_MODE = "BOTH"            # "LONG_ONLY" | "SHORT_ONLY" | "BOTH"
    LONG_AMOUNT_USD = 100.0            # Monto por defecto para operaciones LONG
    SHORT_AMOUNT_USD = 50.0            # Monto por defecto para operaciones SHORT
    LONG_MAX_ENTRY_PRICE = None        # Precio máximo para entrar en LONG (None = sin límite)
    SHORT_MIN_ENTRY_PRICE = None       # Precio mínimo para entrar en SHORT (None = sin límite)
    USE_FRACTIONAL = True              # Soporte de acciones fraccionarias vía notional
    
    # --- MACRO SENTIMENT (Regimes) ---
    MACRO_VIX_MAX = 22.5              # Umbral de "pánico" (No Longs)
    MACRO_DXY_REDUCTION = 0.4         # Reducción de posición si DXY es fuerte
    
    # --- SILVER BULLET WINDOWS (EST) ---
    TIME_WINDOWS = [
        ("10:00", "11:00"),           # Ventana Mañana (Equity)
        ("14:00", "15:00")            # Ventana Tarde (Power Hour)
    ]
    
    ML_THRESHOLD_BULL = 65            # Umbral de IA para señal de compra
    ML_THRESHOLD_BEAR = 35            # Umbral de IA para señal de venta
    
    @staticmethod
    def check_kill_switches(current_equity, day_start_equity, week_start_equity):
        """
        Evalúa si se han superado los límites de pérdida máxima (diaria o semanal).
        Retorna (breaker_activo, nivel, mensaje).
        """
        if not current_equity or current_equity <= 0:
            return False, "NONE", ""
            
        if day_start_equity and day_start_equity > 0:
            daily_loss_pct = (day_start_equity - current_equity) / day_start_equity
            if daily_loss_pct >= TradingBrain.DAILY_MAX_LOSS_PCT:
                return True, "DAILY", f"Pérdida diaria {daily_loss_pct:.1%} >= {TradingBrain.DAILY_MAX_LOSS_PCT:.0%}"
                
        if week_start_equity and week_start_equity > 0:
            weekly_loss_pct = (week_start_equity - current_equity) / week_start_equity
            if weekly_loss_pct >= TradingBrain.WEEKLY_MAX_LOSS_PCT:
                return True, "WEEKLY", f"Pérdida semanal {weekly_loss_pct:.1%} >= {TradingBrain.WEEKLY_MAX_LOSS_PCT:.0%}"
                
        return False, "NONE", ""

    @staticmethod
    def calculate_volatility_adjusted_size(base_amount, current_price, current_atr):
        """
        Ajusta el tamaño de la posición basándose en la volatilidad.
        Si la volatilidad actual (ATR %) es mayor al ATR ideal, reduce la posición.
        """
        if not current_price or current_price <= 0 or not current_atr or current_atr <= 0:
            return base_amount
            
        current_atr_pct = current_atr / current_price
        
        # Factor de ajuste: Ideal ATR / Current ATR
        # Si Current > Ideal, el factor es < 1 (reduce la posición)
        volatility_factor = TradingBrain.ATR_BASE_PERCENT / current_atr_pct
        
        # Limitar para no aumentar de más en mercados muy aburridos, solo para proteger en pánico
        volatility_factor = min(1.0, max(0.2, volatility_factor))
        
        adjusted_amount = base_amount * volatility_factor
        return max(TradingBrain.MINIMUM_TRADE_USD, adjusted_amount)

    @staticmethod
    def initialize():
        """Inicializa el entorno, carga variables y valida la integridad del sistema."""
        load_dotenv()
        env_mode = os.environ.get("TRADING_ENV", "dev").lower()
        if env_mode == "prod":
            load_dotenv(".env.prod")
        elif env_mode == "dev":
            load_dotenv(".env.dev")
            
        TradingBrain.check_integrity()
        # Iniciar logger centralizado si es necesario
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Cerebro Inicializado: Entorno validado (Modo: {env_mode}).")

    @staticmethod
    def get_runtime_config():
        """Obtiene la configuración del usuario desde el archivo JSON de forma segura."""
        if not os.path.exists(CONFIG_FILE):
             # Valores por defecto para evitar que el bot falle por falta de archivo
             default_conf = {
                "auto_trade": False,
                "trade_amount": 100.0,
                "stop_loss_pct": 8.0,
                "take_profit_pct": 15.0,
                "interval": "15m",
                "period": "5d"
             }
             TradingBrain.save_runtime_config(default_conf)
             return default_conf
             
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    @staticmethod
    def save_runtime_config(config_dict):
        """Guarda cualquier cambio en la configuración asegurando la integridad del JSON."""
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_dict, f, indent=4)

    @staticmethod
    def check_integrity():
        """Verifica que los archivos esenciales existan y sean válidos."""
        critical_files = [CONFIG_FILE, MODEL_FILE]
        missing = [f for f in critical_files if not os.path.exists(f)]
        
        if missing:
             # Si faltan archivos, activamos modos de contingencia
             print(f"Alerta de Integridad: Faltan archivos críticos ({', '.join(missing)})")
             # Aquí podríamos forzar la descarga de un modelo fallback o iniciar DB
        
        # Validar DB
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            conn.close()
        except Exception:
            print("Error de Integridad: Base de Datos corrupta o inexistente.")

    @staticmethod
    def get_technical_params():
        """Devuelve los parámetros técnicos centrales para garantizar sincronización."""
        return {
            "smc_atr": TradingBrain.SMC_THRESHOLD_ATR,
            "smc_wick": TradingBrain.SMC_WICK_RATIO,
            "smc_lookback": TradingBrain.SMC_LOOKBACK,
            "smc_breaker": TradingBrain.SMC_BREAKER_MULT,
            "smc_vol_mult": TradingBrain.SMC_VOLUME_MULT,
            "kelly_fraction": TradingBrain.RISK_KELLY_FRACTION,
            "min_rr": TradingBrain.RISK_MIN_RR,
            "ml_bull": TradingBrain.ML_THRESHOLD_BULL,
            "ml_bear": TradingBrain.ML_THRESHOLD_BEAR,
            "vix_max": TradingBrain.MACRO_VIX_MAX,
            "dxy_red": TradingBrain.MACRO_DXY_REDUCTION,
            "windows": TradingBrain.TIME_WINDOWS
        }

    @staticmethod
    def is_silver_bullet_time(current_time=None):
        """
        Verifica si la hora actual está dentro de una ventana de alta probabilidad (EST).
        """
        if current_time is None:
            current_time = datetime.now().strftime("%H:%M")
        
        for start, end in TradingBrain.TIME_WINDOWS:
            if start <= current_time <= end:
                return True
        return False

# Inicialización automática al importar si se desea
# TradingBrain.initialize()
