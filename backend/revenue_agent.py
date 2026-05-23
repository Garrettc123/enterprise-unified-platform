"""
Revenue Automation Agent
=========================
Autonomous agent that runs continuously and:
  1. Scores inbound leads (0-100) by size, budget, intent signals
  2. Forecasts 90-day MRR from historical payment data
  3. Predicts churn risk per account
  4. Fires Linear issues + alerts when thresholds are crossed

Designed to run as a background task inside the FastAPI app
or as a standalone cron job via GitHub Actions.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("revenue_agent")


# ---------------------------------------------------------------------------
# Lead Scoring
# ---------------------------------------------------------------------------

@dataclass
class Lead:
    id: str
    email: str
    company_size: int = 0          # number of employees
    monthly_budget_usd: float = 0  # self-reported or enriched
    intent_signals: int = 0        # page views, demo requests, email opens
    source: str = "organic"        # organic | paid | referral | outbound
    created_at: float = field(default_factory=time.time)


class LeadScorer:
    """
    Scores a lead 0–100 based on:
      - Company size  (30 pts)
      - Budget fit    (30 pts)
      - Intent signals(25 pts)
      - Source quality(15 pts)
    """

    SOURCE_WEIGHTS = {
        "referral": 15,
        "outbound": 12,
        "paid": 10,
        "organic": 8,
        "cold": 5,
    }

    def score(self, lead: Lead) -> int:
        size_score = min(30, int(math.log10(max(lead.company_size, 1)) * 10))
        budget_score = min(30, int(lead.monthly_budget_usd / 1000 * 10))
        intent_score = min(25, lead.intent_signals * 5)
        source_score = self.SOURCE_WEIGHTS.get(lead.source, 5)
        total = size_score + budget_score + intent_score + source_score
        return min(100, total)

    def tier(self, score: int) -> str:
        if score >= 75:
            return "HOT"
        elif score >= 50:
            return "WARM"
        elif score >= 25:
            return "COLD"
        return "DISQUALIFIED"


# ---------------------------------------------------------------------------
# Revenue Forecasting
# ---------------------------------------------------------------------------

@dataclass
class RevenueSnapshot:
    month: int   # UNIX timestamp of month start
    mrr: float   # in USD


class RevenueForecaster:
    """
    Linear trend extrapolation over historical MRR snapshots.
    Returns 90-day MRR projection and growth rate.
    """

    def forecast(self, history: list[RevenueSnapshot], days: int = 90) -> dict:
        if len(history) < 2:
            return {"forecast_mrr": 0.0, "growth_rate_pct": 0.0, "confidence": "low"}

        n = len(history)
        xs = list(range(n))
        ys = [s.mrr for s in history]

        # Simple linear regression
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        numerator = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
        denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = numerator / max(denominator, 0.0001)
        intercept = y_mean - slope * x_mean

        # Project forward ~3 months (each snapshot = 1 month)
        months_forward = days / 30
        forecast_mrr = intercept + slope * (n + months_forward)
        growth_rate = (slope / max(y_mean, 1)) * 100

        confidence = "high" if n >= 6 else "medium" if n >= 3 else "low"

        return {
            "forecast_mrr": round(max(forecast_mrr, 0), 2),
            "current_mrr": round(y_mean, 2),
            "growth_rate_pct": round(growth_rate, 2),
            "months_of_data": n,
            "forecast_horizon_days": days,
            "confidence": confidence,
        }


# ---------------------------------------------------------------------------
# Churn Prediction
# ---------------------------------------------------------------------------

@dataclass
class Account:
    id: str
    customer_email: str
    mrr: float
    days_since_last_login: int = 0
    support_tickets_30d: int = 0
    payment_failures_30d: int = 0
    feature_usage_score: int = 100   # 0-100, higher = more engaged
    contract_days_remaining: int = 365


class ChurnPredictor:
    """
    Risk score 0–100 (higher = more likely to churn).
    Triggers alert at score >= 60.
    """

    def risk_score(self, account: Account) -> int:
        score = 0
        # Disengagement signals
        score += min(30, account.days_since_last_login // 3)
        score += min(20, account.support_tickets_30d * 5)
        score += min(25, account.payment_failures_30d * 12)
        # Engagement health (inverse)
        score += max(0, int((100 - account.feature_usage_score) * 0.20))
        # Contract urgency
        if account.contract_days_remaining < 30:
            score += 15
        elif account.contract_days_remaining < 90:
            score += 7
        return min(100, score)

    def at_risk(self, account: Account) -> bool:
        return self.risk_score(account) >= 60

    def recommendation(self, score: int) -> str:
        if score >= 80:
            return "URGENT: Executive outreach + custom retention offer within 24h"
        elif score >= 60:
            return "Schedule success call + identify adoption blockers this week"
        elif score >= 40:
            return "Send check-in email + share relevant case study"
        return "Healthy — continue standard nurture"


# ---------------------------------------------------------------------------
# Revenue Automation Agent (Orchestrator)
# ---------------------------------------------------------------------------

class RevenueAutomationAgent:
    """
    Autonomous agent that orchestrates LeadScorer, RevenueForecaster,
    and ChurnPredictor. Runs a continuous event loop and fires Linear
    issues + Slack alerts when revenue thresholds are crossed.

    Run standalone:
        agent = RevenueAutomationAgent()
        await agent.run_cycle(leads=[...], accounts=[...], history=[...])
    """

    def __init__(self):
        self.scorer = LeadScorer()
        self.forecaster = RevenueForecaster()
        self.churn = ChurnPredictor()
        self.cycle_count = 0
        self.alerts_fired: list[dict] = []

    async def run_cycle(
        self,
        leads: list[Lead],
        accounts: list[Account],
        history: list[RevenueSnapshot],
    ) -> dict:
        self.cycle_count += 1
        cycle_start = time.time()

        # 1. Score leads
        scored_leads = [
            {"lead_id": l.id, "email": l.email, "score": self.scorer.score(l), "tier": self.scorer.tier(self.scorer.score(l))}
            for l in leads
        ]
        hot_leads = [l for l in scored_leads if l["tier"] == "HOT"]

        # 2. Forecast revenue
        forecast = self.forecaster.forecast(history)

        # 3. Check churn risk
        at_risk = [
            {
                "account_id": a.id,
                "email": a.customer_email,
                "mrr": a.mrr,
                "risk_score": self.churn.risk_score(a),
                "recommendation": self.churn.recommendation(self.churn.risk_score(a)),
            }
            for a in accounts if self.churn.at_risk(a)
        ]

        # 4. Fire alerts
        alerts = []
        if hot_leads:
            alert = {"type": "hot_leads", "count": len(hot_leads), "leads": hot_leads}
            alerts.append(alert)
            await self._fire_alert(alert)

        if at_risk:
            alert = {
                "type": "churn_risk",
                "count": len(at_risk),
                "mrr_at_risk": sum(a["mrr"] for a in at_risk),
                "accounts": at_risk,
            }
            alerts.append(alert)
            await self._fire_alert(alert)

        if forecast.get("growth_rate_pct", 0) < -10:
            alert = {"type": "revenue_decline", "forecast": forecast}
            alerts.append(alert)
            await self._fire_alert(alert)

        result = {
            "cycle": self.cycle_count,
            "duration_ms": round((time.time() - cycle_start) * 1000, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "leads_scored": len(scored_leads),
            "hot_leads": len(hot_leads),
            "accounts_at_risk": len(at_risk),
            "forecast": forecast,
            "alerts_fired": len(alerts),
        }

        logger.info("Revenue cycle %d complete: %s", self.cycle_count, result)
        return result

    async def _fire_alert(self, alert: dict):
        """Post alert to Linear (via env var LINEAR_API_KEY) and log it."""
        self.alerts_fired.append({**alert, "fired_at": datetime.now(timezone.utc).isoformat()})
        logger.warning("[RevenueAlert] %s", alert)

        linear_key = os.environ.get("LINEAR_API_KEY")
        linear_team = os.environ.get("LINEAR_TEAM_ID")
        if not linear_key or not linear_team:
            return

        try:
            import httpx
            title = {
                "hot_leads": f"🔥 {alert.get('count')} Hot Leads Ready for Outreach",
                "churn_risk": f"⚠️ {alert.get('count')} Accounts At Churn Risk (${alert.get('mrr_at_risk', 0):.0f} MRR)",
                "revenue_decline": f"📉 Revenue Decline Detected — Forecast: {alert.get('forecast', {}).get('growth_rate_pct', 0):.1f}% growth",
            }.get(alert["type"], f"Revenue Alert: {alert['type']}")

            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": linear_key, "Content-Type": "application/json"},
                    json={
                        "query": """
                            mutation CreateIssue($title: String!, $teamId: String!) {
                                issueCreate(input: { title: $title, teamId: $teamId, priority: 1 }) {
                                    success issue { id identifier url }
                                }
                            }
                        """,
                        "variables": {"title": title, "teamId": linear_team},
                    },
                    timeout=10,
                )
        except Exception as e:
            logger.error("Failed to fire Linear alert: %s", e)
