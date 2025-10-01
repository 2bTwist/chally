from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timezone as dt_tz, timedelta
from uuid import UUID
from app.models.wallet import WalletEntry
from app.config import settings


class InsufficientFunds(Exception):
    pass

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


async def _advisory_lock_wallet(session: AsyncSession, user_id: UUID):
    """Prevent double-spend races across concurrent requests."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"wallet:{user_id}"})


async def available_balance(session: AsyncSession, user_id: UUID) -> int:
    """Get available balance (same as wallet_balance for now)."""
    return await wallet_balance(session, user_id)


async def debit_tokens(
    session: AsyncSession,
    *,
    user_id: UUID,
    tokens: int,
    external_id: str,
    note: str,
    allocate_fifo: bool = True,
) -> WalletEntry:
    """
    Debit tokens from wallet with FIFO allocation tracking.
    Raises InsufficientFunds if balance is too low.
    """
    if tokens <= 0:
        raise ValueError("tokens must be > 0")

    await _advisory_lock_wallet(session, user_id)

    bal = await available_balance(session, user_id)
    if bal < tokens:
        raise InsufficientFunds(f"need {tokens}, have {bal}")

    # Idempotency: external_id unique
    exists = await session.scalar(select(WalletEntry).where(WalletEntry.external_id == external_id))
    if exists:
        return exists

    withdraw = WalletEntry(
        user_id=user_id,
        type="WITHDRAW",
        amount=-int(tokens),
        currency="usd",
        external_id=external_id,
        note=note,
    )
    session.add(withdraw)
    await session.flush()  # get withdraw.id

    if allocate_fifo:
        # Allocate against oldest DEPOSITs with remaining > 0
        # remaining = deposit.amount - sum(allocation.tokens)
        deposits = (await session.execute(
            select(WalletEntry)
            .where(WalletEntry.user_id == user_id, WalletEntry.type == "DEPOSIT")
            .order_by(WalletEntry.created_at.asc())
        )).scalars().all()

        remaining = tokens
        for dep in deposits:
            if remaining <= 0:
                break
            used = await session.scalar(
                select(func.coalesce(func.sum(text("tokens")), 0))
                .select_from(text("wallet_allocations"))
                .where(text("deposit_entry_id = :d")), {"d": str(dep.id)}
            ) or 0
            avail = int(dep.amount) - int(used)
            if avail <= 0:
                continue
            take = min(avail, remaining)
            await session.execute(text("""
                INSERT INTO wallet_allocations (user_id, withdraw_entry_id, deposit_entry_id, tokens)
                VALUES (:u, :w, :d, :t)
            """), {"u": str(user_id), "w": str(withdraw.id), "d": str(dep.id), "t": int(take)})
            remaining -= take

        if remaining > 0:
            # Should not happen under advisory lock + balance check, but guard anyway
            raise InsufficientFunds("allocation underflow")

    return withdraw


async def credit_tokens(
    session: AsyncSession,
    *,
    user_id: UUID,
    tokens: int,
    external_id: str,
    note: str,
) -> WalletEntry:
    """
    Credit tokens to wallet (for payouts, etc).
    Idempotent by external_id.
    """
    if tokens <= 0:
        raise ValueError("tokens must be > 0")
    
    exists = await session.scalar(select(WalletEntry).where(WalletEntry.external_id == external_id))
    if exists:
        return exists
    
    e = WalletEntry(
        user_id=user_id, 
        type="DEPOSIT", 
        amount=int(tokens),
        currency="usd", 
        external_id=external_id, 
        note=note
    )
    session.add(e)
    return e