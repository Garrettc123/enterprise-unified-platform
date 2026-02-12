from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Dict, List

from ..database import get_db
from ..models import Subscription, Invoice, Payment, Organization
from ..schemas import (
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionResponse,
    InvoiceResponse,
    PaymentCreate,
    PaymentResponse,
)
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/revenue", tags=["revenue"])

# Pricing table (amounts in cents)
PLAN_PRICING = {
    "starter": {"monthly": 9900, "annual": 106800},    # $99/mo or $89/mo billed annually
    "pro": {"monthly": 29900, "annual": 322800},        # $299/mo or $269/mo billed annually
    "enterprise": {"monthly": 99900, "annual": 1078800}, # $999/mo or $899/mo billed annually
}


def _calculate_period_end(start: datetime, billing_cycle: str) -> datetime:
    """Calculate end of billing period from start date and cycle."""
    if billing_cycle == "annual":
        return start.replace(year=start.year + 1)
    # monthly
    month = start.month + 1
    year = start.year
    if month > 12:
        month = 1
        year += 1
    day = min(start.day, 28)  # safe day for all months
    return start.replace(year=year, month=month, day=day)


# ── Subscriptions ──────────────────────────────────────────────

@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    data: SubscriptionCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subscription for an organization."""
    await get_current_user(token, db)

    # Verify organization exists
    org_result = await db.execute(
        select(Organization).where(Organization.id == data.organization_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Check for existing active subscription
    existing = await db.execute(
        select(Subscription).where(
            (Subscription.organization_id == data.organization_id)
            & (Subscription.status.in_(["active", "trialing"]))
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization already has an active subscription",
        )

    amount = PLAN_PRICING[data.plan][data.billing_cycle]
    now = datetime.utcnow()
    period_end = _calculate_period_end(now, data.billing_cycle)

    subscription = Subscription(
        organization_id=data.organization_id,
        plan=data.plan,
        billing_cycle=data.billing_cycle,
        amount=amount,
        currency="USD",
        status="active",
        current_period_start=now,
        current_period_end=period_end,
    )
    db.add(subscription)
    await db.flush()

    # Generate first invoice
    invoice = Invoice(
        subscription_id=subscription.id,
        organization_id=data.organization_id,
        amount=amount,
        currency="USD",
        status="pending",
        due_date=now + timedelta(days=30),
        period_start=now,
        period_end=period_end,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    organization_id: int = Query(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """List subscriptions for an organization."""
    await get_current_user(token, db)
    result = await db.execute(
        select(Subscription)
        .where(Subscription.organization_id == organization_id)
        .order_by(Subscription.created_at.desc())
    )
    return result.scalars().all()


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific subscription."""
    await get_current_user(token, db)
    result = await db.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    data: SubscriptionUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Update (change plan or billing cycle) of an active subscription."""
    await get_current_user(token, db)
    result = await db.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if sub.status != "active":
        raise HTTPException(status_code=400, detail="Only active subscriptions can be updated")

    plan = data.plan or sub.plan
    cycle = data.billing_cycle or sub.billing_cycle
    sub.plan = plan
    sub.billing_cycle = cycle
    sub.amount = PLAN_PRICING[plan][cycle]
    sub.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(sub)
    return sub


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_200_OK)
async def cancel_subscription(
    subscription_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an active subscription."""
    await get_current_user(token, db)
    result = await db.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if sub.status == "canceled":
        raise HTTPException(status_code=400, detail="Subscription is already canceled")

    sub.status = "canceled"
    sub.canceled_at = datetime.utcnow()
    sub.updated_at = datetime.utcnow()
    await db.commit()
    return {"detail": "Subscription canceled"}


# ── Invoices ───────────────────────────────────────────────────

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    organization_id: int = Query(...),
    status_filter: str = Query(None, alias="status"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """List invoices for an organization, optionally filtered by status."""
    await get_current_user(token, db)
    query = select(Invoice).where(Invoice.organization_id == organization_id)
    if status_filter:
        query = query.where(Invoice.status == status_filter)
    query = query.order_by(Invoice.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific invoice."""
    await get_current_user(token, db)
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


# ── Payments ───────────────────────────────────────────────────

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    data: PaymentCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Record a payment against an invoice."""
    await get_current_user(token, db)

    # Look up the invoice
    inv_result = await db.execute(
        select(Invoice).where(Invoice.id == data.invoice_id)
    )
    invoice = inv_result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Invoice is already paid")

    payment = Payment(
        invoice_id=invoice.id,
        organization_id=invoice.organization_id,
        amount=invoice.amount,
        currency=invoice.currency,
        payment_method=data.payment_method,
        status="completed",
        reference_id=data.reference_id,
    )
    db.add(payment)

    # Mark invoice as paid
    invoice.status = "paid"
    invoice.paid_at = datetime.utcnow()

    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/payments", response_model=List[PaymentResponse])
async def list_payments(
    organization_id: int = Query(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """List payments for an organization."""
    await get_current_user(token, db)
    result = await db.execute(
        select(Payment)
        .where(Payment.organization_id == organization_id)
        .order_by(Payment.created_at.desc())
    )
    return result.scalars().all()


# ── Revenue Metrics ────────────────────────────────────────────

@router.get("/metrics")
async def get_revenue_metrics(
    organization_id: int = Query(None, description="Filter by organization, omit for global"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Dict:
    """Get real revenue metrics: MRR, ARR, total collected, outstanding."""
    await get_current_user(token, db)

    # --- Monthly Recurring Revenue (MRR) ---
    mrr_query = select(func.coalesce(func.sum(Subscription.amount), 0)).where(
        Subscription.status.in_(["active", "trialing"])
    )
    if organization_id:
        mrr_query = mrr_query.where(Subscription.organization_id == organization_id)
    mrr_result = await db.execute(mrr_query)
    # All amounts stored as per-cycle; normalise annual subs to monthly
    raw_mrr = float(mrr_result.scalar() or 0)

    # More precise MRR: monthly subs contribute amount; annual subs contribute amount/12
    monthly_mrr_q = select(func.coalesce(func.sum(Subscription.amount), 0)).where(
        Subscription.status.in_(["active", "trialing"]),
        Subscription.billing_cycle == "monthly",
    )
    annual_mrr_q = select(func.coalesce(func.sum(Subscription.amount / 12), 0)).where(
        Subscription.status.in_(["active", "trialing"]),
        Subscription.billing_cycle == "annual",
    )
    if organization_id:
        monthly_mrr_q = monthly_mrr_q.where(Subscription.organization_id == organization_id)
        annual_mrr_q = annual_mrr_q.where(Subscription.organization_id == organization_id)

    monthly_r = await db.execute(monthly_mrr_q)
    annual_r = await db.execute(annual_mrr_q)
    mrr = float(monthly_r.scalar() or 0) + float(annual_r.scalar() or 0)

    # --- Active subscriptions count ---
    active_q = select(func.count(Subscription.id)).where(
        Subscription.status.in_(["active", "trialing"])
    )
    if organization_id:
        active_q = active_q.where(Subscription.organization_id == organization_id)
    active_count = (await db.execute(active_q)).scalar() or 0

    # --- Total collected revenue ---
    collected_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == "completed"
    )
    if organization_id:
        collected_q = collected_q.where(Payment.organization_id == organization_id)
    total_collected = float((await db.execute(collected_q)).scalar() or 0)

    # --- Outstanding (unpaid invoices) ---
    outstanding_q = select(func.coalesce(func.sum(Invoice.amount), 0)).where(
        Invoice.status.in_(["pending", "overdue"])
    )
    if organization_id:
        outstanding_q = outstanding_q.where(Invoice.organization_id == organization_id)
    outstanding = float((await db.execute(outstanding_q)).scalar() or 0)

    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "active_subscriptions": active_count,
        "total_collected": total_collected,
        "outstanding": outstanding,
        "currency": "USD",
    }


@router.get("/metrics/trend")
async def get_revenue_trend(
    days: int = Query(30, ge=1, le=365),
    organization_id: int = Query(None),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> List[Dict]:
    """Get daily collected revenue over the given window."""
    await get_current_user(token, db)
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = (
        select(
            func.date(Payment.created_at).label("date"),
            func.sum(Payment.amount).label("amount"),
        )
        .where(Payment.status == "completed", Payment.created_at >= cutoff)
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
    )
    if organization_id:
        query = query.where(Payment.organization_id == organization_id)

    result = await db.execute(query)
    return [
        {"date": str(row[0]) if row[0] else None, "amount": float(row[1])}
        for row in result.all()
    ]
