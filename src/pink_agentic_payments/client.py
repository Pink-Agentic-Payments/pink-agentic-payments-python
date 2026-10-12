"""Python client for the Pink Agentic AI Payments sandbox REST API.

Every method here maps 1:1 to an operation documented in the sandbox's
OpenAPI spec (https://github.com/Pink-Agentic-Payments/sandbox-examples,
``openapi/openapi.yaml``), which the spec itself says was captured from
live calls against ``https://agentic-sandbox.pinkwallet.com``. See NOTES.md
in this package's repo root for the endpoint-by-method mapping.

Sandbox only: test credentials, no real money moves, production is not
yet available for this product.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence

from .exceptions import PinkAPIError, PinkApprovalPending, PinkPolicyDenied

DEFAULT_BASE_URL = "https://agentic-sandbox.pinkwallet.com"

# Cloudflare (fronting the sandbox) blocks the default Python-urllib user
# agent string outright, so every request needs an explicit one. Confirmed
# by the comment in sandbox-examples/03-python-rest/pay.py and reproduced
# live while building this client (2026-10-12).
_USER_AGENT = "pink-agentic-payments-python/0.1.0"


def _request(
    method: str,
    url: str,
    *,
    bearer_token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> "tuple[int, Dict[str, Any]]":
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw.decode("utf-8", errors="replace")}
        return e.code, payload


def create_sandbox_workspace(
    company: Optional[str] = None,
    email: Optional[str] = None,
    template: str = "coffee",
    base_url: str = DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    """Create a free, disposable sandbox workspace. No auth required.

    Maps to ``POST /v1/sandbox/workspaces`` (the sandbox's signup flow).
    ``template`` is one of ``coffee`` (default), ``startup`` or ``ecommerce``;
    unknown values fall back to ``coffee``. Returns the admin key and one
    agent key per seeded agent, each shown once. These are sandbox-only test
    credentials (``pk_sandbox_admin_...`` / ``pk_sandbox_agent_...``); no real
    money is ever involved.
    """
    body: Dict[str, Any] = {"template": template}
    if company is not None:
        body["company"] = company
    if email is not None:
        body["email"] = email
    status, payload = _request("POST", f"{base_url}/v1/sandbox/workspaces", body=body)
    if status != 201:
        raise PinkAPIError(status, payload.get("error", "failed to create sandbox workspace"), payload)
    return payload


def approve_payment(
    admin_key: str,
    payment_id: str,
    by: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    """``POST /v1/admin/requests/{id}/approve``: approve a pending_human hold.

    Needs the workspace's admin key (``pk_sandbox_admin_...``), not an agent
    key; this is the operation a human takes in ``/console`` to turn a
    ``pending_human`` hold into an issued credential. ``by`` is an optional
    approver display name (defaults to "Sandbox admin" server-side).
    """
    body = {"by": by} if by else {}
    status, payload = _request(
        "POST", f"{base_url}/v1/admin/requests/{payment_id}/approve", bearer_token=admin_key, body=body
    )
    if status >= 400:
        raise PinkAPIError(status, payload.get("error", "failed to approve payment"), payload)
    return payload


def decline_payment(
    admin_key: str,
    payment_id: str,
    by: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    """``POST /v1/admin/requests/{id}/decline``: decline a pending_human hold.

    Needs the workspace's admin key, not an agent key. See :func:`approve_payment`.
    """
    body = {"by": by} if by else {}
    status, payload = _request(
        "POST", f"{base_url}/v1/admin/requests/{payment_id}/decline", bearer_token=admin_key, body=body
    )
    if status >= 400:
        raise PinkAPIError(status, payload.get("error", "failed to decline payment"), payload)
    return payload


def print_mcp_config(agent_key: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """Return a ready-to-paste remote MCP client config (JSON string).

    This is the same ``mcpServers`` / Streamable HTTP shape documented for
    Cline (https://docs.cline.bot/mcp/configuring-mcp-servers) in this
    product's sandbox-examples repo (``llms-install.md``), which Claude
    Desktop and Cursor also use for remote MCP servers over HTTP: a
    ``type: streamableHttp`` entry with the sandbox's ``/mcp`` URL and an
    ``Authorization: Bearer <agent_key>`` header.
    """
    config = {
        "mcpServers": {
            "pink-agentic-payments-sandbox": {
                "type": "streamableHttp",
                "url": f"{base_url}/mcp",
                "headers": {"Authorization": f"Bearer {agent_key}"},
                "disabled": False,
                "autoApprove": [],
            }
        }
    }
    return json.dumps(config, indent=2)


class PinkClient:
    """Agent-side client for the Pink Agentic AI Payments sandbox.

    Every method below calls exactly one documented endpoint of the sandbox
    REST API under ``{base_url}/v1`` using the agent's bearer key. See
    NOTES.md for the full endpoint mapping (including the two admin-only
    endpoints exposed as plain functions, not on this class, since they need
    a different key type).
    """

    def __init__(self, agent_key: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        if not agent_key:
            raise ValueError("agent_key is required (looks like pk_sandbox_agent_...)")
        self.agent_key = agent_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _call(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        status, payload = _request(
            method,
            f"{self.base_url}/v1{path}",
            bearer_token=self.agent_key,
            body=body,
            extra_headers=extra_headers,
            timeout=self.timeout,
        )
        if status >= 400:
            raise PinkAPIError(status, payload.get("error", "sandbox API error"), payload)
        return payload

    # -- identity / policy introspection -------------------------------

    def get_identity(self) -> Dict[str, Any]:
        """``GET /v1/me``: this agent's identity and the workspace summary."""
        return self._call("GET", "/me")

    def get_budget(self) -> Dict[str, Any]:
        """``GET /v1/budget``: this agent's budget, spend-to-date and vault balance."""
        return self._call("GET", "/budget")

    def list_payees(self) -> List[Dict[str, Any]]:
        """``GET /v1/payees``: payees visible to this agent."""
        return self._call("GET", "/payees")["payees"]

    def list_vaults(self) -> List[Dict[str, Any]]:
        """``GET /v1/vaults``: vault(s) this agent can spend from."""
        return self._call("GET", "/vaults")["vaults"]

    def list_rules(self) -> List[Dict[str, Any]]:
        """``GET /v1/rules``: the policy rules that apply to this agent."""
        return self._call("GET", "/rules")["rules"]

    # -- payments ---------------------------------------------------------

    def check_policy(
        self,
        amount: float,
        payee_id: Optional[str] = None,
        payee_name: Optional[str] = None,
        currency: str = "USD",
        purpose: Optional[str] = None,
        reason: Optional[str] = None,
        evidence: Optional[Sequence[str]] = None,
        evidence_flags: Optional[Sequence[str]] = None,
        local_hour: Optional[int] = None,
    ) -> Dict[str, Any]:
        """``POST /v1/payments/check``: dry-run a payment against policy.

        No spend, no side effects. Returns a decision prefixed ``would_``
        (``would_allow`` / ``would_ask`` / ``would_block``) plus the matched
        rule and a human-readable ``trace`` of every rule the engine checked.
        """
        body = _payment_body(
            amount, payee_id, payee_name, currency, purpose, reason, evidence, evidence_flags, local_hour
        )
        return self._call("POST", "/payments/check", body=body)

    def request_payment(
        self,
        amount: float,
        payee_id: Optional[str] = None,
        payee_name: Optional[str] = None,
        currency: str = "USD",
        purpose: Optional[str] = None,
        reason: Optional[str] = None,
        evidence: Optional[Sequence[str]] = None,
        evidence_flags: Optional[Sequence[str]] = None,
        local_hour: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """``POST /v1/payments``: request a real sandbox payment.

        Returns the ``PaymentResult`` with a one-time credential when the
        policy engine decision is ``allowed`` (HTTP 201).

        Raises :class:`PinkApprovalPending` when the decision is
        ``pending_human`` (HTTP 202; poll with :meth:`get_credential`), and
        :class:`PinkPolicyDenied` when the decision is ``blocked``
        (HTTP 403; this exact request will never be allowed). Both
        exceptions carry the full response as ``.payload``.

        Pass ``idempotency_key`` to safely retry: replaying the same key for
        this agent returns the original decision unchanged, with
        ``replayed: true``, at the same HTTP status as the first call.
        """
        body = _payment_body(
            amount, payee_id, payee_name, currency, purpose, reason, evidence, evidence_flags, local_hour
        )
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        status, payload = _request(
            "POST",
            f"{self.base_url}/v1/payments",
            bearer_token=self.agent_key,
            body=body,
            timeout=self.timeout,
        )
        return _raise_for_decision(status, payload)

    def get_payment(self, payment_id: str) -> Dict[str, Any]:
        """``GET /v1/payments/{id}``: look up a payment/hold by id.

        Returns the current ``PaymentResult`` regardless of decision (does
        not raise), so callers can poll a ``pending_human`` hold without
        exception handling. Use :meth:`get_credential` if you want the
        exception-raising version that matches the ``pink.get_credential``
        MCP tool.
        """
        return self._call("GET", f"/payments/{payment_id}")

    def get_credential(self, payment_id: str) -> Dict[str, Any]:
        """Poll a payment/hold and return its credential once decided.

        This is the REST equivalent of the ``pink.get_credential`` MCP tool:
        under the hood it is just ``GET /v1/payments/{id}`` (there is no
        separate "credential" endpoint in the sandbox). Raises
        :class:`PinkApprovalPending` while still ``pending_human``, and
        :class:`PinkPolicyDenied` if it was declined/blocked.
        """
        payload = self.get_payment(payment_id)
        return _raise_for_decision(200, payload)

    def report_receipt(self, payment_id: str, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """``POST /v1/payments/{id}/receipt``: attach a receipt to a payment.

        Raises the agent's trust score. ``receipt`` is a free-form object,
        e.g. ``{"merchant": "...", "total": 420, "reference": "INV-1"}``.
        """
        return self._call("POST", f"/payments/{payment_id}/receipt", body={"receipt": receipt})


def _payment_body(
    amount: float,
    payee_id: Optional[str],
    payee_name: Optional[str],
    currency: str,
    purpose: Optional[str],
    reason: Optional[str],
    evidence: Optional[Sequence[str]],
    evidence_flags: Optional[Sequence[str]],
    local_hour: Optional[int],
) -> Dict[str, Any]:
    body: Dict[str, Any] = {"amount": amount, "currency": currency}
    if payee_id is not None:
        body["payee_id"] = payee_id
    if payee_name is not None:
        body["payee_name"] = payee_name
    if purpose is not None:
        body["purpose"] = purpose
    if reason is not None:
        body["reason"] = reason
    if evidence is not None:
        body["evidence"] = list(evidence)
    if evidence_flags is not None:
        body["evidence_flags"] = list(evidence_flags)
    if local_hour is not None:
        body["local_hour"] = local_hour
    return body


def _raise_for_decision(status: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    decision = payload.get("decision")
    if status == 403 or decision in ("blocked", "declined"):
        raise PinkPolicyDenied(payload)
    if status == 202 or decision == "pending_human":
        raise PinkApprovalPending(payload)
    if status >= 400:
        raise PinkAPIError(status, payload.get("error", "sandbox API error"), payload)
    return payload
