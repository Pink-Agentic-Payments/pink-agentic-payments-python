# pink-agentic-payments

Pink Agentic AI Payments lets AI agents pay within spending rules you set: every payment is checked against per-agent budgets, caps, payee allow-lists and approval rules before a single-use credential is issued.

This is the Python client for Pink Agentic AI Payments by PinkWallet, published by the Pink team. Version 0.1 targets the public **sandbox**. The sandbox is free, needs no signup, uses test money only, and is meant for building and demoing agent integrations. Production is early access; see the waitlist at [pinkwallet.com/agentic](https://pinkwallet.com/agentic/).

JavaScript/TypeScript: https://github.com/Pink-Agentic-Payments/pink-agentic-payments-js

## Install

PyPI release coming soon. Until then, install straight from GitHub:

```bash
pip install git+https://github.com/Pink-Agentic-Payments/pink-agentic-payments-python
```

Future command, once published to PyPI:

```bash
pip install pink-agentic-payments
```

## Quickstart

This really runs against the live sandbox (no signup, no API key to request in advance):

```python
from pink_agentic_payments import create_sandbox_workspace, PinkClient, PinkPolicyDenied, PinkApprovalPending

# 1. Spin up a free sandbox workspace (test money, seeded with agents/payees/rules)
workspace = create_sandbox_workspace(company="My Test Co", template="coffee")
agent_key = workspace["agents"][0]["key"]  # e.g. "Purchasing AI"
print("workspace:", workspace["workspace_id"])

client = PinkClient(agent_key)

# 2. Dry-run a payment (no spend, no side effects)
check = client.check_policy(amount=420, payee_id="p_cc", purpose="beans")
print(check["decision"], "-", check["reason"])  # would_allow - Small supply orders go through

# 3. Make a real (sandbox) payment
try:
    result = client.request_payment(amount=420, payee_id="p_cc", purpose="beans")
    print("allowed, credential:", result["credential"]["type"])
except PinkApprovalPending as e:
    print("pending human approval:", e.payload["who"])
except PinkPolicyDenied as e:
    print("blocked:", e.payload["rule"])
```

## The three outcomes

Every payment request resolves to one of three decisions, each a different HTTP status from the sandbox:

| Decision | HTTP | What happens | Client behavior |
|---|---|---|---|
| `allowed` | 201 | A one-time sandbox credential (card or bank transfer) is issued immediately | `request_payment()` returns the result |
| `pending_human` | 202 | A human must approve in `/console` or via the admin API | `request_payment()` raises `PinkApprovalPending` |
| `blocked` | 403 | No credential, ever, for this exact request | `request_payment()` raises `PinkPolicyDenied` |

Real sandbox output captured while building this package (run `examples/quickstart.py` to reproduce it):

```
allowed:  payment_id=pay_... decision=allowed credential.type=bank_transfer
blocked:  payment_id=pay_... decision=blocked rule="Never: gift cards, cash-like, crypto"
pending:  payment_id=pay_... decision=pending_human who="Maya Chen (Owner)"
```

## Using it as an MCP server instead

The same sandbox is also a remote MCP server at `/mcp`, with tools `pink.get_budget`, `pink.list_payees`, `pink.list_rules`, `pink.check_policy`, `pink.request_payment`, `pink.get_credential`, `pink.report_receipt`. Get a ready-to-paste client config:

```python
from pink_agentic_payments import print_mcp_config
print(print_mcp_config(agent_key))
```

```json
{
  "mcpServers": {
    "pink-agentic-payments-sandbox": {
      "type": "streamableHttp",
      "url": "https://agentic-sandbox.pinkwallet.com/mcp",
      "headers": { "Authorization": "Bearer pk_sandbox_agent_..." },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

This is the remote-MCP-over-HTTP config shape documented for Cline; Claude Desktop and Cursor accept the same `url` + `headers` shape for remote MCP servers.

## Sandbox vs. production

- Everything this client talks to is the **public sandbox**: test credentials (`pk_sandbox_agent_...` / `pk_sandbox_admin_...`), seeded fake balances, one-time fake cards/transfers. No real money ever moves.
- Production for Pink Agentic AI Payments is **early access** (waitlist, not yet generally available): [pinkwallet.com/agentic](https://pinkwallet.com/agentic/).
- Workspaces and keys created in the sandbox can appear/disappear without notice; do not rely on them for anything but development and demos.

## Links

- Docs: https://pinkwallet.com/agentic/developers/
- Live demo (no signup): https://agentic-sandbox.pinkwallet.com/demo
- Example clients in other frameworks (curl, Node MCP SDK, LangGraph, OpenAI Agents SDK, CrewAI, Vercel AI SDK, Haystack): https://github.com/Pink-Agentic-Payments/sandbox-examples
- Open challenge against the sandbox: https://github.com/Pink-Agentic-Payments/overspend-challenge

## Development

```bash
pip install -e . pytest
pytest
python examples/quickstart.py  # hits the live sandbox, creates one workspace
```

## License

MIT, see `LICENSE`.
