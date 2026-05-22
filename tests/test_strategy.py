"""Tests para el motor de estrategia."""
import pandas as pd
import numpy as np
import pytest
from core.strategy import apply_strategy, detect_order_blocks, calculate_kelly_criterion

def make_sample_df(n=200):
    """Genera un DataFrame de prueba con columnas OHLCV."""
    np.random.seed(42)
    closes = 100 + np.cumsum(np.random.randn(n) * 0.5)
    return pd.DataFrame({
        'Open': closes * 0.999,
        'High': closes * 1.002,
        'Low': closes * 0.998,
        'Close': closes,
        'Volume': np.random.randint(1000000, 5000000, n)
    })

class TestApplyStrategy:
    def test_returns_required_columns(self):
        df = make_sample_df()
        result = apply_strategy(df)
        assert 'Signal' in result.columns
        assert 'Score' in result.columns
        assert 'Market_Scenario' in result.columns
    
    def test_score_in_valid_range(self):
        df = make_sample_df()
        result = apply_strategy(df)
        assert result['Score'].between(0, 100).all()
    
    def test_empty_df_returns_empty(self):
        result = apply_strategy(pd.DataFrame())
        assert result.empty

class TestKellyCriterion:
    def test_returns_default_with_no_db(self, tmp_path):
        result = calculate_kelly_criterion(db_path=str(tmp_path / "noexiste.db"))
        assert result == 0.15
    
    def test_kelly_capped_at_25pct(self, tmp_path):
        result = calculate_kelly_criterion()
        assert result <= 0.25
