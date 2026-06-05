from typing import Protocol, Any, Dict, List
from dataclasses import dataclass

@dataclass
class ApprovalRequest:
    action: str
    paths: List[str]
    risk_level: str
    metadata: Dict[str, Any]

@dataclass
class ApprovalDecision:
    approved: bool
    reason: str
    policy_name: str

class ApprovalPolicy(Protocol):
    def evaluate(self, request: ApprovalRequest) -> ApprovalDecision:
        ...
