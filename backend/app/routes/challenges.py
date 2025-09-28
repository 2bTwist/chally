from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.schemas.challenge import ChallengeCreate, ChallengePublic, ParticipantPublic, RulesDSL
from app.services.invite_code import generate_code
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/challenges", tags=["challenges"])

def to_public(ch: Challenge) -> ChallengePublic:
    return ChallengePublic(
        id=ch.id, owner_id=ch.owner_id, name=ch.name, description=ch.description,
        visibility=ch.visibility, invite_code=ch.invite_code,
        starts_at=ch.starts_at, ends_at=ch.ends_at, entry_stake_tokens=ch.entry_stake_tokens,
        rules=RulesDSL.model_validate(ch.rules_json),
        status=ch.status, created_at=ch.created_at
    )

@router.post("", response_model=ChallengePublic, status_code=201)
async def create_challenge(payload: ChallengeCreate, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    # Generate a unique invite code (retry on collision)
    for _ in range(5):
        code = generate_code()
        ch = Challenge(
            owner_id=user.id,
            name=payload.name,
            description=payload.description,
            visibility=payload.visibility,
            invite_code=code,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            entry_stake_tokens=payload.entry_stake_tokens,
            rules_json=payload.rules.model_dump(mode='json'),
            status="active",
        )
        session.add(ch)
        try:
            await session.commit()
            await session.refresh(ch)
            return to_public(ch)
        except IntegrityError:
            await session.rollback()
            continue
    raise HTTPException(status_code=500, detail="Failed to generate unique invite code")

@router.get("/{challenge_id}", response_model=ChallengePublic)
async def get_challenge(challenge_id: str, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return to_public(ch)

@router.get("", response_model=list[ChallengePublic])
async def list_my_challenges(mine: bool = Query(default=True), session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    q = select(Challenge).where(Challenge.owner_id == user.id).order_by(Challenge.created_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return [to_public(c) for c in rows]

@router.post("/{invite_code}/join", response_model=ParticipantPublic, status_code=201)
async def join_by_code(invite_code: str, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    ch = await session.scalar(select(Challenge).where(Challenge.invite_code == invite_code))
    if not ch:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    if ch.status != "active":
        raise HTTPException(status_code=400, detail="Challenge is not active")
    # Prevent duplicate membership
    existing = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
    if existing:
        return ParticipantPublic(id=existing.id, challenge_id=existing.challenge_id, user_id=existing.user_id, joined_at=existing.joined_at)
    p = Participant(challenge_id=ch.id, user_id=user.id)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return ParticipantPublic(id=p.id, challenge_id=p.challenge_id, user_id=p.user_id, joined_at=p.joined_at)