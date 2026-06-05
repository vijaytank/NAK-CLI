import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class SessionContext:
    workspace_root: str
    mode: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
