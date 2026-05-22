from .brain import TradingBrain

def load_env():
    """Proxy al inicializador del Cerebro."""
    TradingBrain.initialize()

def get_config():
    """Proxy al gestor de configuración del Cerebro."""
    return TradingBrain.get_runtime_config()

def save_config(config_dict):
    """Proxy al guardado del Cerebro."""
    TradingBrain.save_runtime_config(config_dict)
