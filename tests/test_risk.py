"""Tests para funciones críticas de gestión de riesgo."""
import pytest
from core.brain import TradingBrain

class TestKillSwitches:
    def test_daily_loss_triggers_at_3pct(self):
        active, level, msg = TradingBrain.check_kill_switches(97, 100, 100)
        assert active is True
        assert level == "DAILY"
    
    def test_weekly_loss_triggers_at_5pct(self):
        # Para probar WEEKLY sin disparar DAILY, pasamos day_start_equity=None
        # así solo se evalúa el circuito semanal
        active, level, msg = TradingBrain.check_kill_switches(95, None, 100)
        assert active is True
        assert level == "WEEKLY"
    
    def test_no_trigger_with_small_loss(self):
        active, _, _ = TradingBrain.check_kill_switches(98, 100, 100)
        assert active is False
    
    def test_handles_zero_equity(self):
        active, _, _ = TradingBrain.check_kill_switches(0, 100, 100)
        assert active is False  # No divide por zero

class TestVolatilityAdjustedSize:
    def test_reduces_size_in_high_vol(self):
        # ATR de 4% -> mucho mayor al ATR ideal de 2% -> debe reducir monto
        result = TradingBrain.calculate_volatility_adjusted_size(100, 100, 4)
        assert result < 100
    
    def test_never_below_minimum(self):
        result = TradingBrain.calculate_volatility_adjusted_size(10, 100, 50)
        assert result >= TradingBrain.MINIMUM_TRADE_USD
