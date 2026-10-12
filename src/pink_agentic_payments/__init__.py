"""Pink Agentic AI Payments: Python client for the public sandbox.

Pink Agentic AI Payments lets AI agents pay within spending rules you set:
every payment is checked against per-agent budgets, caps, payee allow-lists
and approval rules before a single-use credential is issued.

This package talks to the public sandbox only (test credentials, no real
money moves; production is early access, see https://pinkwallet.com/agentic/).
"""
from .client import (
    DEFAULT_BASE_URL,
    PinkClient,
    approve_payment,
    create_sandbox_workspace,
    decline_payment,
    print_mcp_config,
)
from .exceptions import PinkAPIError, PinkApprovalPending, PinkPolicyDenied

__version__ = "0.1.0"

__all__ = [
    "PinkClient",
    "create_sandbox_workspace",
    "approve_payment",
    "decline_payment",
    "print_mcp_config",
    "DEFAULT_BASE_URL",
    "PinkAPIError",
    "PinkApprovalPending",
    "PinkPolicyDenied",
    "__version__",
]
