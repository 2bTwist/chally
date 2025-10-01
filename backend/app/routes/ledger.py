from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.schemas.ledger import LedgerSnapshot
from app.services.ledger import snapshot_for_challenge, close_and_payout, get_platform_revenue_stats
from app.schemas.challenge import RulesDSL

router = APIRouter(tags=["ledger"])

@router.get("/ledger", response_model=LedgerSnapshot)
async def get_ledger(
    challenge_id: UUID = Query(..., alias="challengeId"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")
    # must be a participant (owner auto-joins in your flow)
    part = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
    if not part:
        raise HTTPException(status_code=403, detail="Not a participant of this challenge")
    snap = await snapshot_for_challenge(session, ch.id, user.id)
    return {"challenge_id": ch.id, **snap}

@router.post("/challenges/{challenge_id}/end")
async def end_and_payout(
    challenge_id: UUID = Path(...),
    user=Depends(get_current_user),
):
    from sqlalchemy import text
    from app.db import engine
    from sqlalchemy.ext.asyncio import async_sessionmaker
    
    # Create a fresh session with SERIALIZABLE isolation for challenge closure
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        # Set SERIALIZABLE isolation at the very start of transaction
        await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        
        # Acquire advisory lock for this challenge
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:cid))"), {"cid": str(challenge_id)})
        
        # Lock the challenge row for update
        ch = await session.get(Challenge, challenge_id, with_for_update=True)
        if not ch:
            raise HTTPException(status_code=404, detail="Challenge not found")
        if ch.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Only owner can close the challenge")
            
        result = await close_and_payout(session, ch)
        await session.commit()
        
        return {"challenge_id": str(ch.id), **result}


@router.get("/platform/revenue")
async def get_platform_revenue(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Get platform revenue statistics from forfeited stakes. Admin only."""
    # TODO: Add admin role check here
    # if not user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    stats = await get_platform_revenue_stats(session, days)
    return stats


@router.get("/platform/ledger")
async def get_platform_ledger(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of entries to return"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Get complete platform ledger showing all revenue entries. Admin only."""
    # TODO: Add admin role check here
    # if not user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    from datetime import datetime, timezone as dt_tz, timedelta
    from uuid import UUID
    from app.models.ledger import Ledger
    from app.models.challenge import Challenge
    from app.schemas.ledger import LedgerEntryPublic
    
    cutoff = datetime.now(dt_tz.utc) - timedelta(days=days)
    platform_id = UUID("00000000-0000-0000-0000-000000000000")
    
    # Get all platform revenue entries with challenge details
    entries = (await session.execute(
        select(Ledger, Challenge.name.label("challenge_name"))
        .join(Challenge, Ledger.challenge_id == Challenge.id)
        .where(
            Ledger.participant_id == platform_id,
            Ledger.type == "PLATFORM_REVENUE",
            Ledger.created_at >= cutoff
        )
        .order_by(Ledger.created_at.desc())
        .limit(limit)
    )).all()
    
    # Calculate totals
    total_revenue = sum(int(entry.Ledger.amount) for entry in entries)
    
    return {
        "period_days": days,
        "total_entries": len(entries),
        "total_revenue_tokens": total_revenue,
        "entries": [
            {
                "id": str(entry.Ledger.id),
                "challenge_id": str(entry.Ledger.challenge_id),
                "challenge_name": entry.challenge_name,
                "type": entry.Ledger.type,
                "amount": int(entry.Ledger.amount),
                "note": entry.Ledger.note,
                "created_at": entry.Ledger.created_at,
            } for entry in entries
        ]
    }