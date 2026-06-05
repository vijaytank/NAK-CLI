from typing import Optional, Any
from nak.memory.sqlite_store import SQLiteMemoryStore
from nak.audit.audit_log import AuditLogger

class ExecuteTransaction:
    def __init__(self, db_store: SQLiteMemoryStore, audit_logger: AuditLogger) -> None:
        self.db_store = db_store
        self.audit_logger = audit_logger
        self.initial_audit_size = 0

    async def __aenter__(self) -> "ExecuteTransaction":
        if self.db_store.conn:
            # Explicitly start the transaction
            self.db_store.conn.execute("BEGIN")
        self.initial_audit_size = self.audit_logger.get_current_size()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        if exc_type is not None:
            if self.db_store.conn:
                self.db_store.conn.rollback()
            self.audit_logger.truncate_to_size(self.initial_audit_size)
        else:
            if self.db_store.conn:
                self.db_store.conn.commit()
        return False
