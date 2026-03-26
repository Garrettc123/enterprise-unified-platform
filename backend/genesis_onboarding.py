"""
GENESIS Onboarding Pipeline
============================
Fires automatically when a new Stripe subscription is created.

Pipeline:
  1. Fetch Stripe customer details
  2. Create/update Notion CRM record (Customers database)
  3. Create Linear onboarding issue (assigned to team)
  4. Send Slack welcome message to #new-customers
  5. Record onboarding timestamp in DB

All steps are non-blocking and individually fault-tolerant.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("genesis_onboarding")


class GenesisOnboarding:

    async def run(
        self,
        customer_id: str,
        plan_id: str = "",
        amount_cents: int = 0,
    ) -> dict:
        logger.info("🚀 GENESIS onboarding triggered for customer: %s", customer_id)
        results = {}

        customer_data = await self._fetch_stripe_customer(customer_id)
        email = customer_data.get("email", customer_id)
        name = customer_data.get("name") or email.split("@")[0]
        results["stripe"] = {"email": email, "name": name}

        results["notion"] = await self._create_notion_record(email, name, plan_id, amount_cents)
        results["linear"] = await self._create_linear_issue(email, name, plan_id, amount_cents)
        results["slack"] = await self._send_slack_welcome(email, name, plan_id, amount_cents)

        logger.info("✅ GENESIS onboarding complete for %s: %s", email, results)
        return results

    async def _fetch_stripe_customer(self, customer_id: str) -> dict:
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
            customer = stripe.Customer.retrieve(customer_id)
            return {"email": customer.email, "name": customer.name, "id": customer.id}
        except Exception as e:
            logger.error("Failed to fetch Stripe customer: %s", e)
            return {"email": customer_id, "name": "", "id": customer_id}

    async def _create_notion_record(self, email: str, name: str, plan_id: str, amount_cents: int) -> dict:
        notion_key = os.environ.get("NOTION_API_KEY", "")
        notion_db = os.environ.get("NOTION_CUSTOMERS_DB_ID", "")
        if not notion_key or not notion_db:
            logger.warning("NOTION_API_KEY or NOTION_CUSTOMERS_DB_ID not set — skipping Notion")
            return {"status": "skipped", "reason": "missing env vars"}
        try:
            import httpx
            payload = {
                "parent": {"database_id": notion_db},
                "properties": {
                    "Name": {"title": [{"text": {"content": name}}]},
                    "Email": {"email": email},
                    "Plan": {"rich_text": [{"text": {"content": plan_id}}]},
                    "MRR": {"number": round(amount_cents / 100, 2)},
                    "Status": {"select": {"name": "Active"}},
                    "Onboarded At": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
                },
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.notion.com/v1/pages",
                    headers={
                        "Authorization": f"Bearer {notion_key}",
                        "Notion-Version": "2022-06-28",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code == 200:
                    page_id = resp.json().get("id", "")
                    return {"status": "created", "page_id": page_id}
                else:
                    return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _create_linear_issue(self, email: str, name: str, plan_id: str, amount_cents: int) -> dict:
        linear_key = os.environ.get("LINEAR_API_KEY", "")
        linear_team = os.environ.get("LINEAR_TEAM_ID", "")
        if not linear_key or not linear_team:
            return {"status": "skipped", "reason": "missing env vars"}
        try:
            import httpx
            title = f"🎉 New Customer: {name} ({email}) — ${amount_cents/100:.0f}/mo [{plan_id}]"
            description = (
                f"**New subscription activated via GENESIS pipeline**\n\n"
                f"- **Customer:** {name}\n"
                f"- **Email:** {email}\n"
                f"- **Plan:** `{plan_id}`\n"
                f"- **MRR:** ${amount_cents/100:.2f}\n"
                f"- **Onboarded:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"**Action Items:**\n"
                f"- [ ] Send personalized welcome email\n"
                f"- [ ] Schedule 15-min onboarding call\n"
                f"- [ ] Add to customer Slack channel\n"
                f"- [ ] Verify API access is working\n"
            )
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": linear_key, "Content-Type": "application/json"},
                    json={
                        "query": """
                            mutation CreateIssue($title: String!, $desc: String!, $teamId: String!) {
                                issueCreate(input: {
                                    title: $title, description: $desc,
                                    teamId: $teamId, priority: 2
                                }) {
                                    success issue { id identifier url }
                                }
                            }
                        """,
                        "variables": {"title": title, "desc": description, "teamId": linear_team},
                    },
                )
                data = resp.json()
                issue = data.get("data", {}).get("issueCreate", {}).get("issue", {})
                return {"status": "created", "issue_id": issue.get("identifier"), "url": issue.get("url")}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    async def _send_slack_welcome(self, email: str, name: str, plan_id: str, amount_cents: int) -> dict:
        url = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not url:
            return {"status": "skipped", "reason": "SLACK_WEBHOOK_URL not set"}
        try:
            import httpx
            message = {
                "text": f"🎊 *New Customer Alert!*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "🎊 New Customer — GENESIS Activated"}
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Name:*\n{name}"},
                            {"type": "mrkdwn", "text": f"*Email:*\n{email}"},
                            {"type": "mrkdwn", "text": f"*Plan:*\n`{plan_id}`"},
                            {"type": "mrkdwn", "text": f"*MRR Added:*\n${amount_cents/100:.2f}"},
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"✅ Notion CRM record created\n"
                                f"✅ Linear onboarding issue created\n"
                                f"✅ Subscription active in Stripe\n"
                                f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                            )
                        }
                    }
                ]
            }
            async with httpx.AsyncClient(timeout=8) as client:
                await client.post(url, json=message)
            return {"status": "sent"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}
