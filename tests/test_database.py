"""Tests para el módulo de base de datos."""
import pytest
from core.database import init_db, save_trade, get_trade_history

def test_init_creates_tables(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db_path=db)
    history = get_trade_history(db_path=db)
    assert history is not None

def test_save_and_retrieve_trade(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db_path=db)
    save_trade("AAPL", "AUTO-LONG", 150.0, 100.0, 75, db_path=db)
    history = get_trade_history(db_path=db)
    assert len(history) == 1
    assert history.iloc[0]['ticker'] == "AAPL"
