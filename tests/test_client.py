"""Unit tests for pink_agentic_payments, mocked against the response shapes
documented in sandbox-examples/openapi/openapi.yaml (captured live on
2026-10-01). No network calls."""
import json
import urllib.error
from unittest import mock

import pytest

from pink_agentic_payments import (
    PinkAPIError,
    PinkApprovalPending,
    PinkClient,
    PinkPolicyDenied,
    approve_payment,
    create_sandbox_workspace,
    print_mcp_config,
)


def _http_error(status, payload):
    return urllib.error.HTTPError(
        url="https://agentic-sandbox.pinkwallet.com/v1/x",
        code=status,
        msg="error",
        hdrs=None,
        fp=mock.Mock(read=lambda: json.dumps(payload).encode()),
    )


class _FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_get_budget(monkeypatch):
    budget = {
        "agent": "Purchasing AI",
        "status": "active",
        "monthly_budget": 4000,
        "spent_this_month": 2260,
        "left_this_month": 1740,
        "single_payment_cap": 500,
    }
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(200, budget)) as m:
        client = PinkClient("pk_sandbox_agent_test")
        result = client.get_budget()
    assert result == budget
    req = m.call_args[0][0]
    assert req.full_url == "https://agentic-sandbox.pinkwallet.com/v1/budget"
    assert req.headers["Authorization"] == "Bearer pk_sandbox_agent_test"
    assert "pink-agentic-payments-python" in req.get_header("User-agent")


def test_request_payment_allowed(monkeypatch):
    allowed = {
        "payment_id": "pay_e30e798f2466",
        "decision": "allowed",
        "agent": "Purchasing AI",
        "payee": "Counter Culture Coffee",
        "amount": 420,
        "credential": {"type": "bank_transfer", "sandbox": True, "single_use": True},
    }
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(201, allowed)):
        client = PinkClient("pk_sandbox_agent_test")
        result = client.request_payment(amount=420, payee_id="p_cc", purpose="beans")
    assert result["decision"] == "allowed"
    assert result["credential"]["sandbox"] is True


def test_request_payment_pending_human_raises(monkeypatch):
    pending = {
        "payment_id": "pay_1757bdd8acba",
        "decision": "pending_human",
        "hold_id": "pay_1757bdd8acba",
        "who": "Luis Ortega (Store manager)",
    }
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(202, pending)):
        client = PinkClient("pk_sandbox_agent_test")
        with pytest.raises(PinkApprovalPending) as exc_info:
            client.request_payment(amount=890, payee_id="p_sysco")
    assert exc_info.value.payload["hold_id"] == "pay_1757bdd8acba"
    assert "Luis Ortega" in str(exc_info.value)


def test_request_payment_blocked_raises(monkeypatch):
    blocked = {
        "payment_id": "pay_0608581ece47",
        "decision": "blocked",
        "payee": "giftcards.com",
        "rule": "Never: gift cards, cash-like, crypto",
        "credential": None,
        "why": "matched · block",
    }
    err = _http_error(403, blocked)
    with mock.patch("urllib.request.urlopen", side_effect=err):
        client = PinkClient("pk_sandbox_agent_test")
        with pytest.raises(PinkPolicyDenied) as exc_info:
            client.request_payment(amount=50, payee_name="giftcards.com", purpose="prizes")
    assert exc_info.value.payload["decision"] == "blocked"


def test_unauthorized_raises_generic_api_error(monkeypatch):
    err = _http_error(401, {"error": "Unauthorized: send Authorization: Bearer <key>"})
    with mock.patch("urllib.request.urlopen", side_effect=err):
        client = PinkClient("pk_sandbox_agent_bad")
        with pytest.raises(PinkAPIError) as exc_info:
            client.get_budget()
    assert exc_info.value.status_code == 401


def test_list_payees_unwraps_array(monkeypatch):
    body = {"payees": [{"id": "p_cc", "name": "Counter Culture Coffee"}]}
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(200, body)):
        client = PinkClient("pk_sandbox_agent_test")
        payees = client.list_payees()
    assert payees == body["payees"]


def test_create_sandbox_workspace(monkeypatch):
    created = {
        "workspace_id": "jl43vgtf3j",
        "admin_key": "pk_sandbox_admin_jl43vgtf3j_xxxx",
        "agents": [{"id": "a_purch", "key": "pk_sandbox_agent_jl43vgtf3j_a_purch_xxxx"}],
    }
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(201, created)) as m:
        result = create_sandbox_workspace(company="Test Co", template="coffee")
    assert result["workspace_id"] == "jl43vgtf3j"
    req = m.call_args[0][0]
    sent_body = json.loads(req.data)
    assert sent_body == {"template": "coffee", "company": "Test Co"}
    assert "Authorization" not in req.headers


def test_create_sandbox_workspace_bad_request_raises(monkeypatch):
    err = _http_error(500, {"error": "body must be JSON"})
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(PinkAPIError) as exc_info:
            create_sandbox_workspace()
    assert exc_info.value.status_code == 500


def test_print_mcp_config_shape():
    config_str = print_mcp_config("pk_sandbox_agent_abc123")
    config = json.loads(config_str)
    entry = config["mcpServers"]["pink-agentic-payments-sandbox"]
    assert entry["type"] == "streamableHttp"
    assert entry["url"] == "https://agentic-sandbox.pinkwallet.com/mcp"
    assert entry["headers"]["Authorization"] == "Bearer pk_sandbox_agent_abc123"


def test_approve_payment(monkeypatch):
    approved = {
        "payment_id": "pay_dc9a7a2a3c43",
        "decision": "approved",
        "credential": {"type": "bank_transfer", "sandbox": True},
        "approved_by": ["Sandbox admin"],
    }
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(200, approved)) as m:
        result = approve_payment("pk_sandbox_admin_test", "pay_dc9a7a2a3c43")
    assert result["decision"] == "approved"
    req = m.call_args[0][0]
    assert req.full_url == "https://agentic-sandbox.pinkwallet.com/v1/admin/requests/pay_dc9a7a2a3c43/approve"
    assert req.headers["Authorization"] == "Bearer pk_sandbox_admin_test"


def test_idempotency_key_included_in_body(monkeypatch):
    allowed = {"payment_id": "pay_x", "decision": "allowed", "credential": {}}
    with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(201, allowed)) as m:
        client = PinkClient("pk_sandbox_agent_test")
        client.request_payment(amount=10, payee_id="p_cc", idempotency_key="my-key-1")
    req = m.call_args[0][0]
    sent_body = json.loads(req.data)
    assert sent_body["idempotency_key"] == "my-key-1"
