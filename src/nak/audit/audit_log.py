import os
import json
import time
from typing import Dict, Any, Optional

class AuditLogger:
    def __init__(self, log_path: str) -> None:
        self.log_path = log_path

    def get_current_size(self) -> int:
        if not os.path.exists(self.log_path):
            return 0
        return os.path.getsize(self.log_path)

    def truncate_to_size(self, size: int) -> None:
        if not os.path.exists(self.log_path):
            return
        with open(self.log_path, "a+b") as f:
            f.truncate(size)

    def log(
        self,
        workspace: str,
        task_id: str,
        file_path: str,
        action_type: str,
        hash_before: str,
        hash_after: str,
        approval_decision: str,
        patch_summary: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        
        entry = {
            "timestamp": time.time(),
            "workspace": workspace,
            "task_id": task_id,
            "file_path": file_path,
            "action_type": action_type,
            "hash_before": hash_before,
            "hash_after": hash_after,
            "approval_decision": approval_decision,
            "patch_summary": patch_summary,
            "metadata": metadata or {},
        }
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
