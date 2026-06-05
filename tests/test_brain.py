"""Tests para el Cerebro Central (TradingBrain)."""
import pytest
from core.brain import TradingBrain


class TestSilverBulletTime:
    def test_morning_window_valid(self):
        """10:00-11:00 AM EST debe ser Silver Bullet."""
        assert TradingBrain.is_silver_bullet_time("10:00") is True
        assert TradingBrain.is_silver_bullet_time("10:30") is True
        assert TradingBrain.is_silver_bullet_time("11:00") is True

    def test_afternoon_window_valid(self):
        """14:00-15:00 (2-3 PM) EST debe ser Silver Bullet."""
        assert TradingBrain.is_silver_bullet_time("14:00") is True
        assert TradingBrain.is_silver_bullet_time("14:30") is True
        assert TradingBrain.is_silver_bullet_time("15:00") is True

    def test_outside_window(self):
        """Fuera de ventanas no debe ser Silver Bullet."""
        assert TradingBrain.is_silver_bullet_time("09:59") is False
        assert TradingBrain.is_silver_bullet_time("11:01") is False
        assert TradingBrain.is_silver_bullet_time("13:59") is False
        assert TradingBrain.is_silver_bullet_time("15:01") is False
        assert TradingBrain.is_silver_bullet_time("00:00") is False


class TestCheckKillSwitches:
    def test_daily_loss_triggers_at_3pct(self):
        active, level, msg = TradingBrain.check_kill_switches(97, 100, 100)
        assert active is True
        assert level == "DAILY"

    def test_weekly_loss_triggers_at_5pct(self):
        active, level, msg = TradingBrain.check_kill_switches(95, None, 100)
        assert active is True
        assert level == "WEEKLY"

    def test_no_trigger_with_small_loss(self):
        active, _, _ = TradingBrain.check_kill_switches(98, 100, 100)
        assert active is False

    def test_handles_zero_equity(self):
        active, _, _ = TradingBrain.check_kill_switches(0, 100, 100)
        assert active is False

    def test_handles_none_equity(self):
        active, _, _ = TradingBrain.check_kill_switches(None, 100, 100)
        assert active is False

    def test_handles_none_day_start(self):
        active, _, _ = TradingBrain.check_kill_switches(100, None, None)
        assert active is False

    def test_exactly_at_threshold_triggers(self):
        """Pérdida diaria exactamente al 3% debe disparar."""
        active, level, _ = TradingBrain.check_kill_switches(97.0, 100.0, 100.0)
        assert active is True

    def test_below_threshold_no_trigger(self):
        """Pérdida al 2.99% no debe disparar."""
        active, _, _ = TradingBrain.check_kill_switches(97.01, 100.0, 100.0)
        assert active is False


class TestVolatilityAdjustedSize:
    def test_reduces_size_in_high_vol(self):
        result = TradingBrain.calculate_volatility_adjusted_size(100, 100, 4)
        assert result < 100

    def test_never_below_minimum(self):
        result = TradingBrain.calculate_volatility_adjusted_size(10, 100, 50)
        assert result >= TradingBrain.MINIMUM_TRADE_USD

    def test_returns_base_when_atr_zero(self):
        result = TradingBrain.calculate_volatility_adjusted_size(100, 100, 0)
        assert result == 100

    def test_returns_base_when_price_zero(self):
        result = TradingBrain.calculate_volatility_adjusted_size(100, 0, 1)
        assert result == 100

    def test_low_volatility_does_not_exceed_base(self):
        """ATR bajo que haría factor > 1 debe cap a 1.0 (no aumentar)."""
        result = TradingBrain.calculate_volatility_adjusted_size(100, 100, 0.5)
        assert result <= 100


class TestVIXThresholds:
    def test_vix_low_returns_60(self):
        """VIX < 15 → threshold 60."""
        from core.brain import TradingBrain
        thresholds = TradingBrain.VIX_SCORE_THRESHOLDS
        # VIX=14 → buscar primer par donde 14 < vmax → (15, 60)
        result = next(t for vmax, t in thresholds if 14 < vmax)
        assert result == 60

    def test_vix_medium_returns_65(self):
        """VIX=20 → buscar primer par: 20 < 22 → (22, 65)."""
        thresholds = TradingBrain.VIX_SCORE_THRESHOLDS
        result = next(t for vmax, t in thresholds if 20 < vmax)
        assert result == 65

    def test_vix_high_returns_75(self):
        """VIX=25 → 25 < 99 → (99, 75)."""
        thresholds = TradingBrain.VIX_SCORE_THRESHOLDS
        result = next(t for vmax, t in thresholds if 25 < vmax)
        assert result == 75


class TestTechnicalParams:
    def test_returns_all_keys(self):
        params = TradingBrain.get_technical_params()
        expected_keys = [
            "smc_atr", "smc_wick", "smc_lookback", "smc_breaker",
            "smc_vol_mult", "kelly_fraction", "min_rr",
            "ml_bull", "ml_bear", "vix_max", "dxy_red", "windows"
        ]
        for key in expected_keys:
            assert key in params, f"Falta clave: {key}"

    def test_windows_formato_correcto(self):
        params = TradingBrain.get_technical_params()
        windows = params["windows"]
        assert len(windows) == 2
        for start, end in windows:
            assert ":" in start
            assert ":" in end