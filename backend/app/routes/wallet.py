from __future__ import annotations
import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.auth_deps import get_current_user
from app.schemas.wallet import WalletSnapshot, WalletEntryPublic, CreateDepositRequest, CreateDepositResponse
from app.services.wallet import wallet_balance, wallet_entries

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("", response_model=WalletSnapshot)
async def get_wallet(session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    bals = await wallet_balance(session, user.id)
    rows = await wallet_entries(session, user.id)
    return {
        "balance": bals,
        "entries": [
            WalletEntryPublic(
                id=r.id, type=r.type, amount=int(r.amount), currency=r.currency,
                external_id=r.external_id, note=r.note, created_at=r.created_at
            ) for r in rows
        ]
    }

@router.post("/deposit/checkout", response_model=CreateDepositResponse)
async def create_deposit_checkout(payload: CreateDepositRequest, user=Depends(get_current_user)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    if payload.tokens <= 0:
        raise HTTPException(status_code=400, detail="tokens must be > 0")

    # 1 token = 1 cent (by default). If TOKEN_PRICE_USD_CENTS != 1, we scale.
    usd_cents = payload.tokens * max(1, settings.token_price_usd_cents)
    stripe.api_key = settings.stripe_secret_key

    # Create a one-off payment via Checkout
    session = stripe.checkout.Session.create(
        mode="payment",
        client_reference_id=str(user.id),  # we'll use this in the webhook
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "PeerPush Token Top-up"},
                "unit_amount": int(usd_cents),
            },
            "quantity": 1,
        }],
        payment_intent_data={
            "metadata": {
                "user_id": str(user.id),
                "tokens_requested": str(payload.tokens),
            }
        },
        success_url=str(payload.success_url) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=str(payload.cancel_url),
    )

    return CreateDepositResponse(checkout_url=session["url"], session_id=session["id"])