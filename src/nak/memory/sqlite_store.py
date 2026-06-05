import json
import sqlite3
import time
from typing import List, Optional, Dict, Any
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repl_chat_history (
                session_id TEXT,
                timestamp REAL,
                role TEXT,
                content TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        self.conn.commit()

    @property
    def schema_version(self) -> str:
        return "1.1.0"

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

    async def save_chat_message(self, session_id: str, role: str, content: str) -> None:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO repl_chat_history (session_id, timestamp, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, time.time(), role, content)
        )
        self.conn.commit()

    async def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM repl_chat_history 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
            """,
            (session_id,)
        )
        rows = cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def clear_chat_history(self, session_id: str) -> None:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM repl_chat_history WHERE session_id = ?",
            (session_id,)
        )
        self.conn.commit()

    async def get_last_session_id(self) -> Optional[str]:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT session_id FROM repl_chat_history 
            ORDER BY timestamp DESC LIMIT 1
            """
        )
        row = cursor.fetchone()
        return row["session_id"] if row else None

    async def get_config(self, key: str) -> Optional[str]:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    async def set_config(self, key: str, value: str) -> None:
        if not self.conn:
            raise RuntimeError("Database not connected")
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
