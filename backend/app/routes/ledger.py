from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.schemas.ledger import LedgerSnapshot
from app.services.ledger import snapshot_for_challenge, close_and_payout
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