"""Tests para el sistema de auditoría (audit_log)."""
import pytest
import sqlite3
import os
import tempfile
from core.database import init_db, save_audit_log, get_audit_logs


@pytest.fixture
def temp_db():
    """Crea una BD temporal para tests de auditoría."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    # Cleanup
    try:
        os.unlink(path)
        for suffix in ["-wal", "-shm"]:
            if os.path.exists(path + suffix):
                os.unlink(path + suffix)
    except Exception:
        pass


class TestSaveAuditLog:
    def test_save_basic_event(self, temp_db):
        save_audit_log("TEST_EVENT", db_path=temp_db)
        df = get_audit_logs(limit=1, db_path=temp_db)
        assert len(df) == 1
        assert df.iloc[0]["event_type"] == "TEST_EVENT"

    def test_save_with_details(self, temp_db):
        details = {"action": "test", "value": 42}
        save_audit_log("CONFIG_CHANGE", details=details, db_path=temp_db)
        df = get_audit_logs(limit=1, db_path=temp_db)
        row = df.iloc[0]
        assert row["event_type"] == "CONFIG_CHANGE"
        assert row["details_json"] is not None

    def test_save_with_ip_and_agent(self, temp_db):
        save_audit_log(
            "LOGIN",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            db_path=temp_db
        )
        df = get_audit_logs(limit=1, db_path=temp_db)
        row = df.iloc[0]
        assert row["ip_address"] == "192.168.1.1"
        assert row["user_agent"] == "TestAgent/1.0"

    def test_save_with_severity(self, temp_db):
        for sev in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
            save_audit_log("TEST", severity=sev, db_path=temp_db)
        df = get_audit_logs(limit=10, db_path=temp_db)
        severities = df["severity"].tolist()
        for sev in ["INFO", "WARNING", "ERROR", "CRITICAL"]:
            assert sev in severities

    def test_timestamp_is_set(self, temp_db):
        save_audit_log("TIMESTAMP_TEST", db_path=temp_db)
        df = get_audit_logs(limit=1, db_path=temp_db)
        row = df.iloc[0]
        assert row["timestamp"] is not None
        assert len(row["timestamp"]) > 0


class TestGetAuditLogs:
    def test_returns_empty_df_no_db(self):
        df = get_audit_logs(db_path="/tmp/nonexistent_xyz.db")
        assert df.empty

    def test_filter_by_event_type(self, temp_db):
        save_audit_log("TYPE_A", db_path=temp_db)
        save_audit_log("TYPE_A", db_path=temp_db)
        save_audit_log("TYPE_B", db_path=temp_db)

        df_a = get_audit_logs(event_type="TYPE_A", db_path=temp_db)
        df_b = get_audit_logs(event_type="TYPE_B", db_path=temp_db)

        assert len(df_a) == 2
        assert len(df_b) == 1

    def test_respects_limit(self, temp_db):
        for i in range(10):
            save_audit_log("BULK_TEST", db_path=temp_db)

        df = get_audit_logs(limit=5, db_path=temp_db)
        assert len(df) == 5

    def test_order_descending(self, temp_db):
        save_audit_log("FIRST", db_path=temp_db)
        import time
        time.sleep(0.01)  # Asegurar timestamp diferente
        save_audit_log("LAST", db_path=temp_db)

        df = get_audit_logs(limit=2, db_path=temp_db)
        # El más reciente primero
        assert df.iloc[0]["event_type"] == "LAST"