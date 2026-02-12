import logging
from typing import List

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import Payment
from ..routers.auth import get_current_user, oauth2_scheme
from ..schemas import PaymentIntentCreate, PaymentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _get_stripe_client() -> stripe.StripeClient:
    """Create and return a Stripe client using the configured secret key."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


@router.post(
    "/create-payment-intent",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_intent(
    payment_data: PaymentIntentCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe PaymentIntent and store the payment record."""
    current_user = await get_current_user(token, db)
    client = _get_stripe_client()

    try:
        intent = client.payment_intents.create(
            params={
                "amount": payment_data.amount,
                "currency": payment_data.currency,
                "description": payment_data.description,
                "receipt_email": payment_data.receipt_email,
                "metadata": {"user_id": str(current_user.id)},
            }
        )
    except stripe.StripeError as e:
        logger.error("Stripe error creating payment intent: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Payment service error",
        ) from e

    payment = Payment(
        user_id=current_user.id,
        stripe_payment_intent_id=intent.id,
        amount=payment_data.amount,
        currency=payment_data.currency,
        status=intent.status or "pending",
        description=payment_data.description,
        receipt_email=payment_data.receipt_email,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get a payment by ID for the current user."""
    current_user = await get_current_user(token, db)

    result = await db.execute(
        select(Payment).where(
            (Payment.id == payment_id) & (Payment.user_id == current_user.id)
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return payment


@router.get("/", response_model=List[PaymentResponse])
async def list_payments(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """List all payments for the current user."""
    current_user = await get_current_user(token, db)

    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
    )
    return result.scalars().all()


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events to update payment statuses."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as e:
        logger.error("Invalid webhook payload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from e
    except stripe.SignatureVerificationError as e:
        logger.error("Invalid webhook signature: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e

    if event.type in (
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    ):
        intent = event.data.object
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == intent.get("id")
            )
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = intent.get("status", payment.status)
            payment.payment_method_type = next(
                iter(intent.get("payment_method_types", [])), None
            )
            payment.stripe_customer_id = intent.get("customer")
            await db.commit()

    return {"status": "ok"}
