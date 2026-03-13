from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

class BrokerClient:
    def __init__(self, api_key, secret_key, paper=True):
        """
        Inicia la conexión con el Broker (Alpaca).
        paper=True = Dinero Falso (Paper Trading).
        paper=False = Dinero Real (Live Trading).
        """
        try:
            self.client = TradingClient(api_key, secret_key, paper=paper)
            self.account = self.client.get_account()
            self.connected = True
        except Exception as e:
            self.connected = False
            self.error = str(e)

    def is_connected(self):
        return self.connected

    def get_account_info(self):
        if self.connected:
            return {
                "buying_power": float(self.account.buying_power),
                "equity": float(self.account.equity),
                "status": self.account.status,
                "currency": self.account.currency
            }
        return None

    def execute_trade(self, symbol, side, qty=None, notional=None):
        """
        Envía una orden al mercado.
        
        Parámetros:
        - symbol: Ticker (ej: "AAPL.MX" → se limpia a "AAPL")
        - side: 'buy' o 'sell'
        - qty: Cantidad de acciones (enteras). Usar esto O notional, no ambos.
        - notional: Monto en dólares (ej: 5.0 = compra $5 USD de la acción).
                    Permite comprar fracciones de acciones.
        
        Si se pasa notional, se ignora qty.
        """
        if not self.connected:
            return False, "Broker no conectado"

        try:
            # Limpiar .MX para Alpaca (solo opera stocks de EE.UU.)
            clean_symbol = symbol.replace('.MX', '').replace('.mx', '')

            order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL

            if notional and notional > 0:
                # Orden por MONTO EN DÓLARES (acciones fraccionarias)
                order_data = MarketOrderRequest(
                    symbol=clean_symbol,
                    notional=round(float(notional), 2),
                    side=order_side,
                    time_in_force=TimeInForce.DAY  # DAY es requerido para notional
                )
                label = f"${notional:.2f} USD"
            elif qty and qty > 0:
                # Orden por CANTIDAD de acciones
                order_data = MarketOrderRequest(
                    symbol=clean_symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=TimeInForce.GTC
                )
                label = f"{qty} acción(es)"
            else:
                return False, "Debes especificar qty o notional"

            order = self.client.submit_order(order_data=order_data)
            emoji = "📈" if side == 'buy' else "📉"
            return True, f"{emoji} Orden {side.upper()} ejecutada: {clean_symbol} por {label}. ID: {order.id}"

        except Exception as e:
            return False, f"Error ejecutando orden: {str(e)}"
