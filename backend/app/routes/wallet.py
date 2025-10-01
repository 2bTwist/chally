from __future__ import annotations
import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.auth_deps import get_current_user
from app.schemas.wallet import WalletSnapshot, WalletEntryPublic, CreateDepositRequest, CreateDepositResponse, WithdrawRequest, WithdrawResponse
from app.services.wallet import wallet_balance, wallet_entries, debit_tokens, InsufficientFunds
from sqlalchemy import select, func, text
from datetime import datetime, timezone as dt_tz, timedelta
from app.models.wallet import WalletEntry
import uuid

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
async def create_deposit_checkout(payload: CreateDepositRequest, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    if payload.tokens <= 0:
        raise HTTPException(status_code=400, detail="tokens must be > 0")

    # Daily deposit limit check
    now = datetime.now(dt_tz.utc)
    day_ago = now - timedelta(days=1)
    spent_today = await session.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0))
        .where(WalletEntry.user_id == user.id, WalletEntry.type == "DEPOSIT", WalletEntry.created_at >= day_ago)
    ) or 0
    if int(spent_today) + payload.tokens > settings.max_deposit_tokens_day:
        raise HTTPException(status_code=400, detail="Daily deposit limit exceeded")

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


@router.post("/withdraw/refund", response_model=WithdrawResponse)
async def withdraw_refund(payload: WithdrawRequest, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    """Withdraw tokens back to card via Stripe refunds (FIFO by deposit lots)."""
    if settings.withdraw_mode != "refund":
        raise HTTPException(status_code=400, detail="Withdrawals are disabled")

    # Lock wallet and ensure sufficient balance
    try:
        withdraw = await debit_tokens(
            session,
            user_id=user.id,
            tokens=payload.tokens,
            external_id=f"refund_req:{user.id}:{uuid.uuid4().hex[:8]}",
            note="refund_to_card",
            allocate_fifo=True,
        )
    except InsufficientFunds:
        raise HTTPException(status_code=402, detail="Insufficient wallet balance")

    # Build FIFO refund across deposits using allocations *remaining* per deposit
    stripe.api_key = settings.stripe_secret_key
    tokens_left = payload.tokens
    cents_per_token = max(1, settings.token_price_usd_cents)

    # Deposits with remaining (unallocated) and within refund window
    window_start = datetime.now(dt_tz.utc) - timedelta(days=settings.refund_window_days)
    deposits = (await session.execute(
        select(WalletEntry)
        .where(WalletEntry.user_id == user.id, WalletEntry.type == "DEPOSIT", WalletEntry.created_at >= window_start)
        .order_by(WalletEntry.created_at.asc())
    )).scalars().all()

    refunds_made = []
    for dep in deposits:
        if tokens_left <= 0:
            break
        used = await session.scalar(
            select(func.coalesce(func.sum(text("tokens")), 0))
            .select_from(text("wallet_allocations"))
            .where(text("deposit_entry_id = :d")), {"d": str(dep.id)}
        ) or 0
        remaining = int(dep.amount) - int(used)
        if remaining <= 0:
            continue
        take = min(remaining, tokens_left)
        # Stripe refund (against the deposit's payment_intent)
        if not dep.external_id:
            continue  # safety: should always be set
        try:
            r = stripe.Refund.create(
                payment_intent=dep.external_id,
                amount=int(take * cents_per_token),
            )
            refunds_made.append((r["id"], take))
            # Audit row
            await session.execute(text("""
                INSERT INTO wallet_refunds (user_id, stripe_refund_id, amount_cents, tokens, currency, status)
                VALUES (:u, :rid, :amt, :tok, 'usd', 'succeeded')
            """), {"u": str(user.id), "rid": r["id"], "amt": int(take * cents_per_token), "tok": int(take)})
            tokens_left -= take
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"Stripe refund failed: {e}")

    if tokens_left > 0:
        # Could not refund the full amount (not enough refundable lots)
        # Reverse the portion of wallet WITHDRAW we couldn't send back to card:
        # Simply add ADJUST +tokens_left to restore wallet.
        session.add(WalletEntry(user_id=user.id, type="ADJUST", amount=int(tokens_left), currency="usd", note="refund_unavailable_restore"))
        tokens_refunded = payload.tokens - tokens_left
    else:
        tokens_refunded = payload.tokens

    await session.commit()
    return WithdrawResponse(requested=payload.tokens, refunded=tokens_refunded, stripe_refunds=[rid for (rid, _t) in refunds_made])