"""Exceptions for the Pink Agentic AI Payments sandbox client."""
from __future__ import annotations

from typing import Any, Dict, Optional


class PinkAPIError(Exception):
    """Raised for any sandbox API error response that isn't a policy decision.

    Covers malformed requests (400), auth failures (401), not-found (404) and
    the sandbox's known quirk of returning 500 for a non-JSON request body.
    """

    def __init__(self, status_code: int, message: str, payload: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        self.payload = payload or {}
        super().__init__(f"HTTP {status_code}: {message}")


class PinkPolicyDenied(PinkAPIError):
    """A payment was blocked by policy (decision=blocked, HTTP 403).

    ``payload`` is the full ``PaymentResult`` body, including ``rule`` and
    ``why`` describing which rule matched.
    """

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        reason = payload.get("rule") or payload.get("why") or "blocked by policy"
        super().__init__(403, reason, payload)


class PinkApprovalPending(PinkAPIError):
    """A payment is awaiting human approval (decision=pending_human, HTTP 202).

    ``payload`` includes ``hold_id`` (poll with ``PinkClient.get_credential``
    or ``GET /v1/payments/{id}``), ``who`` (the approver) and ``expires_at``.
    """

    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        who = payload.get("who", "a human approver")
        super().__init__(202, f"pending approval from {who}", payload)
