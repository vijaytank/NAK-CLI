import json
import sqlite3
from typing import List, Optional
from nak.protocols.memory_store import MemoryStore, ChangeRecord

class SQLiteMemoryStore(MemoryStore):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        import os
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS changes (
                id TEXT PRIMARY KEY,
                workspace TEXT,
                request TEXT,
                files_touched TEXT,
                patch_summary TEXT,
                validation_status TEXT,
                metadata TEXT
            )
        """)
        self.conn.commit()

    @property
    def schema_version(self) -> str:
        return "1.0.0"

    async def save_change(self, change: ChangeRecord) -> str:
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO changes 
            (id, workspace, request, files_touched, patch_summary, validation_status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                change.id,
                change.workspace,
                change.request,
                json.dumps(change.files_touched),
                change.patch_summary,
                change.validation_status,
                json.dumps(change.metadata),
            ),
        )
        return change.id

    async def get_changes(self, workspace: str) -> List[ChangeRecord]:
        if not self.conn:
            raise RuntimeError("Database not connected")
            
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, workspace, request, files_touched, patch_summary, validation_status, metadata FROM changes WHERE workspace = ?",
            (workspace,),
        )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append(
                ChangeRecord(
                    id=row["id"],
                    workspace=row["workspace"],
                    request=row["request"],
                    files_touched=json.loads(row["files_touched"]),
                    patch_summary=row["patch_summary"],
                    validation_status=row["validation_status"],
                    metadata=json.loads(row["metadata"]),
                )
            )
        return results

    async def get_by_id(self, id: str) -> Optional[ChangeRecord]:
        if not self.conn:
            raise RuntimeError("Database not connected")
            
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, workspace, request, files_touched, patch_summary, validation_status, metadata FROM changes WHERE id = ?",
            (id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ChangeRecord(
            id=row["id"],
            workspace=row["workspace"],
            request=row["request"],
            files_touched=json.loads(row["files_touched"]),
            patch_summary=row["patch_summary"],
            validation_status=row["validation_status"],
            metadata=json.loads(row["metadata"]),
        )

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
