"""Tests de concurrencia en base de datos SQLite con WAL mode."""
import pytest
import os
import tempfile
import threading
import time
from core.database import init_db, save_trade, get_trade_history, save_audit_log


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    try:
        os.unlink(path)
        for suffix in ["-wal", "-shm"]:
            if os.path.exists(path + suffix):
                os.unlink(path + suffix)
    except Exception:
        pass


class TestConcurrentWrites:
    def test_parallel_trade_writes(self, temp_db):
        """10 hilos escribiendo trades simultaneamente sin deadlocks."""
        errors = []
        barrier = threading.Barrier(10, timeout=10)

        def write_trade(i):
            try:
                barrier.wait()
                save_trade(f"TICKER{i % 5}", "LONG", 100.0 + i, 50.0, 70, db_path=temp_db)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=write_trade, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"Errores concurrentes: {errors}"

        df = get_trade_history(limit=20, db_path=temp_db)
        assert len(df) >= 10

    def test_writes_during_reads(self, temp_db):
        """3 escritores + 2 lectores simultaneos sin bloqueos."""
        # Insertar datos base
        for i in range(5):
            save_trade("BASE", "LONG", 100, 10, 50, db_path=temp_db)

        errors = []
        start = threading.Event()

        def writer():
            try:
                start.wait()
                for i in range(5):
                    save_trade("WRITE", "LONG", 100, 10, 50, db_path=temp_db)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Writer: {e}")

        def reader():
            try:
                start.wait()
                for _ in range(5):
                    df = get_trade_history(limit=10, db_path=temp_db)
                    assert len(df) > 0
                    time.sleep(0.02)
            except Exception as e:
                errors.append(f"Reader: {e}")

        writers = [threading.Thread(target=writer) for _ in range(3)]
        readers = [threading.Thread(target=reader) for _ in range(2)]
        all_threads = writers + readers

        for t in all_threads:
            t.start()
        start.set()
        for t in all_threads:
            t.join(timeout=15)

        assert len(errors) == 0, f"Errores read/write: {errors}"


class TestConcurrentAuditLog:
    def test_parallel_audit_writes(self, temp_db):
        """5 hilos escribiendo audit_log simultaneamente."""
        errors = []

        def write_audit(i):
            try:
                save_audit_log("CONCURRENT_TEST", details={"thread": i}, db_path=temp_db)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=write_audit, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errores audit concurrente: {errors}"