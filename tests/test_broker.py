"""Tests para el BrokerClient (exponential backoff y estado degradado)."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.broker import BrokerClient


class TestBrokerClientInit:
    def test_init_sets_degraded_false_by_default(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.return_value.get_account.return_value = MagicMock()
            bc = BrokerClient("key", "secret", paper=True)
            assert bc.degraded is False

    def test_init_sets_connected_true_on_success(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.return_value.get_account.return_value = MagicMock()
            bc = BrokerClient("key", "secret", paper=True)
            assert bc.connected is True

    def test_init_sets_connected_false_on_error(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.side_effect = Exception("Connection refused")
            bc = BrokerClient("key", "secret", paper=True)
            assert bc.connected is False


class TestSafeApiCall:
    def setup_method(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.return_value.get_account.return_value = MagicMock()
            self.bc = BrokerClient("key", "secret", paper=True)

    def test_successful_call_returns_result(self):
        mock_func = Mock(return_value="success")
        result = self.bc._safe_api_call(mock_func)
        assert result == "success"
        assert self.bc.degraded is False

    def test_recovery_after_success(self):
        """Tras un fallo, si la llamada siguiente es exitosa, se resetea degraded."""
        self.bc._consecutive_failures = 2
        self.bc.degraded = True
        mock_func = Mock(return_value="ok")
        result = self.bc._safe_api_call(mock_func)
        assert result == "ok"
        assert self.bc._consecutive_failures == 0
        assert self.bc.degraded is False

    def test_rate_limit_triggers_longer_delay(self):
        """HTTP 429 debe usar delay >= 30s."""
        mock_func = Mock(side_effect=[
            Exception("429 Too Many Requests"),
            "ok"
        ])
        with patch("time.sleep") as mock_sleep:
            result = self.bc._safe_api_call(mock_func)
            assert result == "ok"
            # Verificar que el delay fue al menos 30s
            delay_args = [call[0][0] for call in mock_sleep.call_args_list]
            assert any(d >= 30.0 for d in delay_args), f"Esperado delay >=30s, obtenido: {delay_args}"

    def test_consecutive_failures_set_degraded(self):
        """2 fallos consecutivos activan flag degraded."""
        mock_func = Mock(side_effect=Exception("Network error"))
        with patch("time.sleep"):
            for _ in range(3):
                try:
                    self.bc._safe_api_call(mock_func)
                except Exception:
                    pass
        assert self.bc._consecutive_failures >= 2
        assert self.bc.degraded is True

    def test_exponential_backoff_increases_delay(self):
        """Los delays deben crecer: 2s → 4s → 8s."""
        mock_func = Mock(side_effect=[
            Exception("fail1"),
            Exception("fail2"),
            "ok"
        ])
        delays = []
        with patch("time.sleep", side_effect=lambda d: delays.append(d)):
            result = self.bc._safe_api_call(mock_func)
            assert result == "ok"

        # Deberían ser ~2s y ~4s (con jitter)
        assert len(delays) == 2
        assert delays[0] >= 2.0, f"Primer delay: {delays[0]}"
        assert delays[1] >= 4.0, f"Segundo delay: {delays[1]}"


class TestIsConnected:
    def test_returns_true_when_connected(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.return_value.get_account.return_value = MagicMock()
            bc = BrokerClient("key", "secret", paper=True)
            assert bc.is_connected() is True

    def test_returns_false_when_not_connected(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.side_effect = Exception("Fail")
            bc = BrokerClient("key", "secret", paper=True)
            assert bc.is_connected() is False


class TestResetDegraded:
    def test_resets_failures_and_flag(self):
        with patch("core.broker.TradingClient", autospec=True) as mock_tc:
            mock_tc.return_value.get_account.return_value = MagicMock()
            bc = BrokerClient("key", "secret", paper=True)
            bc._consecutive_failures = 5
            bc.degraded = True
            bc._reset_degraded()
            assert bc._consecutive_failures == 0
            assert bc.degraded is False