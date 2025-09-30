from __future__ import annotations
import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db import get_session
from app.services.wallet import credit_deposit_idempotent

router = APIRouter(tags=["stripe"])

@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_session),
):
    if not settings.stripe_webhook_secret or not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=payload.decode("utf-8"),
            sig_header=stripe_signature or "",
            secret=settings.stripe_webhook_secret,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {e}")

    stripe.api_key = settings.stripe_secret_key

    # Handle both paths; we use payment_intent id as idempotency key.
    if event["type"] == "checkout.session.completed":
        sess = event["data"]["object"]
        if sess.get("payment_status") == "paid":
            pi_id = sess.get("payment_intent")
            user_id = sess.get("client_reference_id") or (sess.get("metadata") or {}).get("user_id")
            amount_cents = int(sess.get("amount_total") or 0)
            if pi_id and user_id and amount_cents > 0:
                from uuid import UUID
                created = await credit_deposit_idempotent(db, user_id=UUID(user_id), external_id=pi_id, usd_cents=amount_cents)
                if created:
                    await db.commit()
        return {"ok": True}

    if event["type"] == "payment_intent.succeeded":
        pi = event["data"]["object"]
        user_id = (pi.get("metadata") or {}).get("user_id")
        amount_cents = int(pi.get("amount_received") or pi.get("amount") or 0)
        if pi.get("status") == "succeeded" and user_id and amount_cents > 0:
            from uuid import UUID
            created = await credit_deposit_idempotent(db, user_id=UUID(user_id), external_id=pi["id"], usd_cents=amount_cents)
            if created:
                await db.commit()
        return {"ok": True}

    # Ignore other events
    return {"ignored": event["type"]}