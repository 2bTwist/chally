from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from app.models.wallet import WalletEntry
from app.config import settings

async def wallet_balance(session: AsyncSession, user_id: UUID) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0)).where(WalletEntry.user_id == user_id)
    )
    return int(total or 0)

async def wallet_entries(session: AsyncSession, user_id: UUID) -> list[WalletEntry]:
    return (await session.execute(
        select(WalletEntry).where(WalletEntry.user_id == user_id).order_by(WalletEntry.created_at.desc())
    )).scalars().all()

async def credit_deposit_idempotent(session: AsyncSession, *, user_id: UUID, external_id: str, usd_cents: int) -> bool:
    """
    Credit tokens based on fiat received. Idempotent by external_id.
    Returns True if a new entry was created; False if duplicate.
    """
    if usd_cents <= 0:
        return False

    # 1 token = TOKEN_PRICE_USD_CENTS cents; default = 1 (1 token = 1 cent)
    tokens = usd_cents // max(1, settings.token_price_usd_cents)
    if tokens <= 0:
        return False

    exists = await session.scalar(
        select(WalletEntry).where(WalletEntry.external_id == external_id)
    )
    if exists:
        return False

    session.add(WalletEntry(
        user_id=user_id,
        type="DEPOSIT",
        amount=int(tokens),
        currency="usd",
        external_id=external_id,
        note="stripe_deposit",
    ))
    return True