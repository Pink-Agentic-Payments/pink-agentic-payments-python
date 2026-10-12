#!/usr/bin/env python3
"""Live end-to-end example against the real Pink Agentic AI Payments sandbox.

Creates ONE sandbox workspace (test money, no signup), then shows the three
payment outcomes (allowed, blocked, pending human approval) and the full
human-approval lifecycle: request -> pending_human -> an admin approves it ->
a one-time credential is issued.

Note: the sandbox's "coffee" template has a company-wide rule, "Between 11pm
and 6am: ask the owner" (America/Chicago). That rule is checked against real
wall-clock time for actual payments (POST /v1/payments), even though you can
pass local_hour to override it for the *dry-run* check (POST /v1/payments/check)
-- this is a live-verified quirk, see NOTES.md. If you run this script at
night in Chicago, step 4 below may come back pending_human instead of
allowed; the script handles both outcomes.

Usage:
    python3 examples/quickstart.py
"""
from pink_agentic_payments import (
    PinkApprovalPending,
    PinkClient,
    PinkPolicyDenied,
    approve_payment,
    create_sandbox_workspace,
    print_mcp_config,
)


def main():
    print("== 1. Create a sandbox workspace (coffee template) ==")
    workspace = create_sandbox_workspace(company="pink-agentic-payments quickstart", template="coffee")
    print("workspace_id:", workspace["workspace_id"])
    agents = {a["id"]: a for a in workspace["agents"]}
    admin_key = workspace["admin_key"]
    purchasing_key = agents["a_purch"]["key"]
    print("agents:", list(agents.keys()))

    client = PinkClient(purchasing_key)

    print("\n== 2. Identity + budget (Purchasing AI) ==")
    print(client.get_identity())
    print(client.get_budget())

    print("\n== 3. Dry-run a small payment (would_allow expected) ==")
    check = client.check_policy(amount=420, payee_id="p_cc", purpose="20kg espresso beans", local_hour=14)
    print(check["decision"], "-", check["reason"])

    print("\n== 4. Request the same payment for real ==")
    hold_id = None
    try:
        result = client.request_payment(amount=420, payee_id="p_cc", purpose="20kg espresso beans")
        print("decision: allowed | credential.type:", result["credential"]["type"])
    except PinkApprovalPending as e:
        hold_id = e.payload["hold_id"]
        print("decision: pending_human | hold_id:", hold_id, "| who:", e.payload.get("who"),
              "| rule:", e.payload.get("rule"))
        print("(this happens outside 6am-11pm America/Chicago, see NOTES.md)")

    print("\n== 5. BLOCKED: try to pay a blocked category (gift cards) ==")
    try:
        client.request_payment(amount=50, payee_name="giftcards.com", purpose="prizes")
        print("UNEXPECTED: not blocked")
    except PinkPolicyDenied as e:
        print("decision: blocked | rule:", e.payload.get("rule"))

    if hold_id is None:
        print("\n== 6. PENDING HUMAN: a bigger payment to force approval ==")
        try:
            client.request_payment(amount=2500, payee_id="p_cc", purpose="emergency bulk order")
            print("UNEXPECTED: not pending")
        except PinkApprovalPending as e:
            hold_id = e.payload["hold_id"]
            print("decision: pending_human | hold_id:", hold_id, "| who:", e.payload.get("who"))

    print("\n== 7. Admin approves the pending hold (full approval lifecycle) ==")
    approved = approve_payment(admin_key, hold_id, by="quickstart admin")
    print("decision:", approved["decision"], "| credential.type:", approved.get("credential", {}).get("type"))

    print("\n== 8. Poll it again via get_credential (now resolved, no exception) ==")
    final = client.get_credential(hold_id)
    print("decision:", final["decision"], "| credential:", final.get("credential"))

    print("\n== 9. Report a receipt for the approved payment ==")
    receipt_result = client.report_receipt(hold_id, {"merchant": "Counter Culture Coffee", "total": 420})
    print(receipt_result)

    print("\n== 10. MCP config for this agent ==")
    print(print_mcp_config(purchasing_key))


if __name__ == "__main__":
    main()
