import tempfile
from pathlib import Path
import pytest
from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.audit.audit_log import AuditLogger
from nak.memory.transaction import ExecuteTransaction
from nak.protocols.memory_store import ChangeRecord

@pytest.fixture
def temp_db_and_audit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "memory.db"
        audit_path = Path(tmpdir) / "audit.log"
        
        # Initialize store
        store = SQLiteMemoryStore(str(db_path))
        store.connect()
        
        # Initialize audit logger
        logger = AuditLogger(str(audit_path))
        
        try:
            yield store, logger, audit_path
        finally:
            store.close()

@pytest.mark.asyncio
async def test_transaction_commit(temp_db_and_audit):
    store, logger, audit_path = temp_db_and_audit
    
    change = ChangeRecord(
        id="c1",
        workspace="ws",
        request="test request",
        files_touched=["test.txt"],
        patch_summary="patched",
        validation_status="validated",
        metadata={}
    )
    
    async with ExecuteTransaction(store, logger):
        await store.save_change(change)
        logger.log("ws", "t1", "test.txt", "write", "hash1", "hash2", "approved", "patched")
        
    # Verify both are committed
    changes = await store.get_changes("ws")
    assert len(changes) == 1
    assert changes[0].id == "c1"
    
    # Audit log should have content
    assert audit_path.exists()
    assert "test.txt" in audit_path.read_text()

@pytest.mark.asyncio
async def test_transaction_rollback_on_error(temp_db_and_audit):
    store, logger, audit_path = temp_db_and_audit
    
    change = ChangeRecord(
        id="c2",
        workspace="ws",
        request="test request",
        files_touched=["test.txt"],
        patch_summary="patched",
        validation_status="validated",
        metadata={}
    )
    
    # Initial audit log contents
    audit_path.write_text("initial log line\n")
    
    try:
        async with ExecuteTransaction(store, logger):
            await store.save_change(change)
            logger.log("ws", "t1", "test.txt", "write", "hash1", "hash2", "approved", "patched")
            raise ValueError("simulated crash")
    except ValueError:
        pass
        
    # Verify store rolled back
    changes = await store.get_changes("ws")
    assert len(changes) == 0
    
    # Verify audit log rolled back to initial content (truncated) and appended TRANSACTION_ROLLBACK entry
    log_text = audit_path.read_text()
    assert log_text.startswith("initial log line\n")
    assert "TRANSACTION_ROLLBACK" in log_text

@pytest.mark.asyncio
async def test_repl_chat_history(temp_db_and_audit):
    store, logger, audit_path = temp_db_and_audit
    
    # Save a couple of messages
    await store.save_chat_message("session_1", "user", "hello AI")
    await store.save_chat_message("session_1", "assistant", "hello User")
    
    # Save to a different session
    await store.save_chat_message("session_2", "user", "other thread")
    
    # Retrieve session 1
    history1 = await store.get_chat_history("session_1")
    assert len(history1) == 2
    assert history1[0]["role"] == "user"
    assert history1[0]["content"] == "hello AI"
    assert history1[1]["role"] == "assistant"
    assert history1[1]["content"] == "hello User"
    
    # Retrieve session 2
    history2 = await store.get_chat_history("session_2")
    assert len(history2) == 1
    assert history2[0]["content"] == "other thread"
    
    # Clear session 1
    await store.clear_chat_history("session_1")
    history1_cleared = await store.get_chat_history("session_1")
    assert len(history1_cleared) == 0
    # Session 2 should remain
    assert len(await store.get_chat_history("session_2")) == 1

    # Get last session id
    assert await store.get_last_session_id() == "session_2"


@pytest.mark.asyncio
async def test_transaction_id_and_logs(temp_db_and_audit):
    store, logger, audit_path = temp_db_and_audit

    async with ExecuteTransaction(store, logger) as tx:
        assert tx.transaction_id is not None
        # Should be a UUID string
        import uuid
        uuid.UUID(tx.transaction_id)

    # After successful transaction, verify that TRANSACTION_COMMIT was logged in audit entries
    entries = logger.read_entries()
    assert len(entries) == 1
    assert entries[0]["action_type"] == "TRANSACTION_COMMIT"
    assert entries[0]["metadata"]["transaction_id"] == tx.transaction_id


@pytest.mark.asyncio
async def test_transaction_rollback_log(temp_db_and_audit):
    store, logger, audit_path = temp_db_and_audit

    tx_id = None
    try:
        async with ExecuteTransaction(store, logger) as tx:
            tx_id = tx.transaction_id
            raise ValueError("rollback me")
    except ValueError:
        pass

    # Audit log should contain TRANSACTION_ROLLBACK even after rollback/truncation
    # Wait, if we truncate the log to the size before the transaction, does the rollback entry survive?
    # Ah! The rollback log entry is written AFTER or BEFORE truncation?
    # If we truncate, any entries written DURING the transaction are deleted, but the rollback entry
    # itself should be written AFTER we truncate (or we don't truncate it away).
    # Yes! The rollback entry should be written after truncation so it is preserved in the audit log.
    entries = logger.read_entries()
    assert len(entries) == 1
    assert entries[0]["action_type"] == "TRANSACTION_ROLLBACK"
    assert entries[0]["metadata"]["transaction_id"] == tx_id


@pytest.mark.asyncio
async def test_transaction_truncation_failure_handling(temp_db_and_audit, caplog):
    store, logger, audit_path = temp_db_and_audit

    # Mock truncate_to_size to raise an OSError
    def raise_error(size):
        raise OSError("disk full")
    logger.truncate_to_size = raise_error

    import logging
    with caplog.at_level(logging.ERROR):
        try:
            async with ExecuteTransaction(store, logger):
                raise ValueError("trigger rollback")
        except ValueError:
            pass

        assert any("rollback" in record.message.lower() or "truncate" in record.message.lower() for record in caplog.records)

