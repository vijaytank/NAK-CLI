import uuid
import logging
from typing import Optional, Any
from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.audit.audit_log import AuditLogger

class ExecuteTransaction:
    def __init__(self, db_store: SQLiteMemoryStore, audit_logger: AuditLogger) -> None:
        self.db_store = db_store
        self.audit_logger = audit_logger
        self.initial_audit_size = 0
        self.initial_entry_count = 0
        self.transaction_id = str(uuid.uuid4())

    async def __aenter__(self) -> "ExecuteTransaction":
        if self.db_store.conn:
            # Explicitly start the transaction
            self.db_store.conn.execute("BEGIN")
            self.db_store._in_explicit_transaction = True
        self.initial_audit_size = self.audit_logger.get_current_size()
        self.initial_entry_count = self.audit_logger.get_entry_count()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        if self.db_store.conn:
            self.db_store._in_explicit_transaction = False
        if exc_type is not None:
            if self.db_store.conn:
                self.db_store.conn.rollback()
            try:
                self.audit_logger.truncate_to_size(self.initial_audit_size)
            except Exception as e:
                logging.error(f"Failed to truncate audit log during rollback: {str(e)}")
            
            try:
                self.audit_logger.log(
                    workspace="unknown",
                    task_id="",
                    file_path="",
                    action_type="TRANSACTION_ROLLBACK",
                    hash_before="",
                    hash_after="",
                    approval_decision="",
                    patch_summary="",
                    metadata={"transaction_id": self.transaction_id}
                )
            except Exception:
                pass
        else:
            if self.db_store.conn:
                self.db_store.conn.commit()
            try:
                self.audit_logger.log(
                    workspace="unknown",
                    task_id="",
                    file_path="",
                    action_type="TRANSACTION_COMMIT",
                    hash_before="",
                    hash_after="",
                    approval_decision="",
                    patch_summary="",
                    metadata={"transaction_id": self.transaction_id}
                )
            except Exception:
                pass
        return False

