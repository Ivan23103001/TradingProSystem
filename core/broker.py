from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
import math


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
        """Obtiene info de la cuenta con datos actualizados."""
        if self.connected:
            try:
                self.account = self.client.get_account()
            except Exception:
                pass
            return {
                "buying_power": float(self.account.buying_power),
                "equity": float(self.account.equity),
                "status": self.account.status,
                "currency": self.account.currency
            }
        return None

    def get_open_positions(self):
        if not self.connected:
            return []
        try:
            positions = self.client.get_all_positions()
            parsed = []
            for p in positions:
                parsed.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc) * 100,
                    "current_price": float(p.current_price),
                    "avg_entry_price": float(p.avg_entry_price) if hasattr(p, 'avg_entry_price') and p.avg_entry_price else 0.0,
                    "side": "long" if float(p.qty) > 0 else "short"
                })
            return parsed
        except Exception:
            return []

    # =========================================================================
    # POST-MORTEM: Análisis de Órdenes Cerradas
    # =========================================================================

    def get_closed_orders(self, symbol=None, limit=50):
        """
        Obtiene órdenes cerradas/completadas recientes para análisis post-mortem.
        Permite determinar si un trade fue cerrado por Stop Loss, Take Profit, o manualmente.
        """
        if not self.connected:
            return []
        try:
            request = GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                limit=limit,
                nested=True
            )
            orders = self.client.get_all_orders(filter=request)
            result = []
            for o in orders:
                order_info = {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side),
                    "type": str(o.type),
                    "status": str(o.status),
                    "filled_qty": float(o.filled_qty) if o.filled_qty else 0,
                    "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else 0,
                    "order_class": str(o.order_class) if hasattr(o, 'order_class') and o.order_class else "simple",
                    "created_at": str(o.created_at),
                    "filled_at": str(o.filled_at) if o.filled_at else "",
                    "sl_triggered": False,
                    "tp_triggered": False,
                }
                # Analizar legs de bracket orders (hijos SL/TP)
                if hasattr(o, 'legs') and o.legs:
                    for leg in o.legs:
                        leg_type = str(leg.type).lower() if leg.type else ""
                        leg_status = str(leg.status).lower() if leg.status else ""
                        if 'stop' in leg_type:
                            order_info['sl_triggered'] = 'filled' in leg_status
                        elif 'limit' in leg_type:
                            order_info['tp_triggered'] = 'filled' in leg_status
                result.append(order_info)

            if symbol:
                result = [o for o in result if o.get('symbol') == symbol]
            return result
        except Exception:
            return []

    def determine_close_reason(self, symbol):
        """
        Analiza las órdenes recientes en Alpaca para determinar por qué se cerró una posición.

        Returns: 'STOP_LOSS', 'TAKE_PROFIT', 'MANUAL', o 'UNKNOWN'
        """
        orders = self.get_closed_orders(symbol=symbol, limit=10)
        if not orders:
            return 'UNKNOWN'

        for order in orders:
            # Bracket order con legs
            if order.get('sl_triggered'):
                return 'STOP_LOSS'
            if order.get('tp_triggered'):
                return 'TAKE_PROFIT'
            # Orden stop independiente que se llenó
            order_type = order.get('type', '').lower()
            order_status = order.get('status', '').lower()
            if 'stop' in order_type and 'filled' in order_status:
                return 'STOP_LOSS'
            if 'limit' in order_type and 'filled' in order_status:
                return 'TAKE_PROFIT'

        return 'MANUAL'

    def close_position(self, symbol):
        """Cierra una posición abierta inmediatamente (market order de cierre)."""
        if not self.connected:
            return False, "Broker no conectado"
        try:
            self.client.close_position(symbol)
            return True, f"Posición {symbol} cerrada exitosamente"
        except Exception as e:
            return False, f"Error cerrando {symbol}: {str(e)}"

    # =========================================================================
    # EJECUCIÓN DE TRADES CON PROTECCIÓN INTELIGENTE
    # =========================================================================

    def execute_trade(self, symbol, side, qty=None, notional=None, take_profit_price=None, stop_loss_price=None, current_price=None):
        """
        Envía una orden al mercado con protección inteligente de SL/TP.

        Alpaca NO soporta bracket orders con 'notional' (acciones fraccionarias).
        Por eso:
          - Si notional + SL/TP: convierte a qty (si >= 1 acción) para usar bracket.
          - Si qty < 1: coloca orden simple y retorna has_bracket=False para que
            el bot_worker monitoree la posición en software.

        Args:
            current_price: Precio de mercado actual (último Close). Si es None,
                           se estima del promedio SL+TP como fallback legacy.

        Returns:
            (success: bool, message: str, has_bracket: bool)
            has_bracket indica si el broker gestiona el SL/TP automáticamente.
        """
        if not self.connected:
            return False, "Broker no conectado", False

        try:
            clean_symbol = symbol.strip()
            order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL

            # Preparar legs de bracket si se proporcionan SL/TP
            wants_bracket = bool(take_profit_price and stop_loss_price)
            if wants_bracket:
                tp_req = TakeProfitRequest(limit_price=round(take_profit_price, 2))
                sl_req = StopLossRequest(stop_price=round(stop_loss_price, 2))
            else:
                tp_req = None
                sl_req = None

            # =================================================================
            # PATH 1: Orden por MONTO EN DÓLARES (Notional / Fracciones)
            # =================================================================
            if notional and notional > 0:
                has_bracket = False

                if wants_bracket:
                    # Usar precio de mercado real si está disponible; fallback al promedio SL/TP
                    ref_price = current_price if current_price and current_price > 0 else ((take_profit_price + stop_loss_price) / 2)
                    # Intentar convertir notional → qty para usar bracket
                    try:
                        estimated_qty = math.floor(notional / ref_price)

                        if estimated_qty >= 1:
                            # Suficiente para al menos 1 acción: usar BRACKET
                            order_data = MarketOrderRequest(
                                symbol=clean_symbol,
                                qty=int(estimated_qty),
                                side=order_side,
                                time_in_force=TimeInForce.GTC,
                                take_profit=tp_req,
                                stop_loss=sl_req,
                                order_class=OrderClass.BRACKET
                            )
                            order = self.client.submit_order(order_data=order_data)
                            emoji = "📈" if side == 'buy' else "📉"
                            return (
                                True,
                                f"{emoji} BRACKET {side.upper()}: {clean_symbol} x{estimated_qty} acc "
                                f"(SL: ${stop_loss_price:.2f} / TP: ${take_profit_price:.2f}). ID: {order.id}",
                                True
                            )
                    except Exception:
                        pass  # Fallback a orden simple

                # Fallback: Orden notional simple (sin bracket del broker)
                order_data = MarketOrderRequest(
                    symbol=clean_symbol,
                    notional=round(float(notional), 2),
                    side=order_side,
                    time_in_force=TimeInForce.DAY
                )
                order = self.client.submit_order(order_data=order_data)
                emoji = "📈" if side == 'buy' else "📉"
                sw_warn = " ⚠️ MONITOREO SOFTWARE (bracket no soportado en notional)" if wants_bracket else ""
                return (
                    True,
                    f"{emoji} Orden {side.upper()}: {clean_symbol} ${notional:.2f} USD.{sw_warn} ID: {order.id}",
                    False
                )

            # =================================================================
            # PATH 2: Orden por CANTIDAD de acciones (Qty)
            # =================================================================
            elif qty and qty > 0:
                order_data = MarketOrderRequest(
                    symbol=clean_symbol,
                    qty=int(qty),
                    side=order_side,
                    time_in_force=TimeInForce.GTC,
                    take_profit=tp_req if wants_bracket else None,
                    stop_loss=sl_req if wants_bracket else None,
                    order_class=OrderClass.BRACKET if wants_bracket else None
                )
                order = self.client.submit_order(order_data=order_data)
                emoji = "📈" if side == 'buy' else "📉"
                bracket_info = f" (Bracket SL: ${stop_loss_price:.2f} / TP: ${take_profit_price:.2f})" if wants_bracket else ""
                return (
                    True,
                    f"{emoji} Orden {side.upper()}: {clean_symbol} x{qty} acc.{bracket_info} ID: {order.id}",
                    wants_bracket
                )

            else:
                return False, "Debes especificar qty o notional", False

        except Exception as e:
            return False, f"Error ejecutando orden: {str(e)}", False
