from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, exists
from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.models.user import User
from app.schemas.challenge import ChallengeCreate, ChallengePublic, ParticipantPublic, RulesDSL, ParticipantWithUser
from app.services.invite_code import generate_code
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone as dt_tz

router = APIRouter(prefix="/challenges", tags=["challenges"])

def compute_runtime_state(ch: Challenge, now: datetime) -> str:
    if ch.status in ("canceled", "deleted"):
        return ch.status
    if now < ch.starts_at:
        return "upcoming"
    if ch.starts_at <= now <= ch.ends_at:
        return "started"
    return "ended"

async def hydrate_public(session: AsyncSession, ch: Challenge, user_id) -> ChallengePublic:
    now = datetime.now(dt_tz.utc)
    participant_count = await session.scalar(
        select(func.count()).select_from(Participant).where(Participant.challenge_id == ch.id)
    )
    is_owner = (ch.owner_id == user_id)
    is_participant = await session.scalar(
        select(exists().where(Participant.challenge_id == ch.id, Participant.user_id == user_id))
    )
    return ChallengePublic(
        id=ch.id, owner_id=ch.owner_id, name=ch.name, description=ch.description,
        visibility=ch.visibility, invite_code=ch.invite_code,
        starts_at=ch.starts_at, ends_at=ch.ends_at, entry_stake_tokens=ch.entry_stake_tokens,
        rules=RulesDSL.model_validate(ch.rules_json),
        status=ch.status, created_at=ch.created_at,
        participant_count=int(participant_count or 0),
        is_owner=is_owner,
        is_participant=bool(is_participant),
        runtime_state=compute_runtime_state(ch, now),
    )

def to_public(ch: Challenge) -> ChallengePublic:
    # Legacy helper - keeping for backward compatibility but prefer hydrate_public
    return ChallengePublic(
        id=ch.id, owner_id=ch.owner_id, name=ch.name, description=ch.description,
        visibility=ch.visibility, invite_code=ch.invite_code,
        starts_at=ch.starts_at, ends_at=ch.ends_at, entry_stake_tokens=ch.entry_stake_tokens,
        rules=RulesDSL.model_validate(ch.rules_json),
        status=ch.status, created_at=ch.created_at,
        participant_count=0, is_owner=False, is_participant=False, runtime_state="upcoming"
    )

@router.post("", response_model=ChallengePublic, status_code=201)
async def create_challenge(
    payload: ChallengeCreate,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    x_client_tz: str | None = Header(default=None, alias="X-Client-Timezone"),
):
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
            await session.flush()  # get ch.id without commit

            # Owner becomes participant #1
            # Determine timezone for owner participant
            rules = ch.rules_json or {}
            scope = ((rules.get("time_window") or {}).get("scope")) or "participant_local"
            ch_tz = ((rules.get("time_window") or {}).get("timezone"))
            owner_tz = x_client_tz or (ch_tz if scope == "challenge_tz" and ch_tz else "UTC")

            session.add(Participant(challenge_id=ch.id, user_id=user.id, timezone=owner_tz))

            await session.commit()
            await session.refresh(ch)
            return await hydrate_public(session, ch, user.id)
        except IntegrityError:
            await session.rollback()
            continue
    raise HTTPException(status_code=500, detail="Failed to generate unique invite code")

@router.get("/mine", response_model=list[ChallengePublic])
async def list_my_challenges(session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    q = select(Challenge).where(Challenge.owner_id == user.id).order_by(Challenge.created_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return [await hydrate_public(session, c, user.id) for c in rows]

@router.get("/joined", response_model=list[ChallengePublic])
async def list_joined(session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    q = (
        select(Challenge)
        .join(Participant, Participant.challenge_id == Challenge.id)
        .where(Participant.user_id == user.id)
        .order_by(Challenge.created_at.desc())
    )
    rows = (await session.execute(q)).scalars().all()
    return [await hydrate_public(session, c, user.id) for c in rows]

@router.get("/{challenge_id}", response_model=ChallengePublic)
async def get_challenge(challenge_id: str, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return await hydrate_public(session, ch, user.id)

@router.get("/{challenge_id}/participants", response_model=list[ParticipantWithUser])
async def list_participants(challenge_id: str, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")
    # (Optional: owners-only restriction; for MVP we allow any participant to view)
    q = (
        select(Participant.id, User.id, User.username, Participant.joined_at)
        .join(User, User.id == Participant.user_id)
        .where(Participant.challenge_id == ch.id)
        .order_by(Participant.joined_at.asc())
    )
    rows = (await session.execute(q)).all()
    return [
        ParticipantWithUser(
            participant_id=pid, user_id=uid, username=uname, joined_at=joined_at
        ) for (pid, uid, uname, joined_at) in rows
    ]

@router.post("/{invite_code}/join", response_model=ParticipantPublic, status_code=201)
async def join_by_code(
    invite_code: str,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    x_client_tz: str | None = Header(default=None, alias="X-Client-Timezone"),
    body: dict | None = Body(default=None),
):
    ch = await session.scalar(select(Challenge).where(Challenge.invite_code == invite_code))
    if not ch:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    if user.id == ch.owner_id:
        raise HTTPException(status_code=409, detail="Owner is already part of this challenge")
    # Gate by admin status and start time
    now = datetime.now(dt_tz.utc)
    if ch.status != "active":
        raise HTTPException(status_code=400, detail="Challenge is not active")
    if now >= ch.starts_at:
        raise HTTPException(status_code=400, detail="Challenge has already started; joining is closed")

    # Determine timezone from header or body
    tz = x_client_tz or (body or {}).get("timezone")
    
    # Default: if DSL is challenge_tz, use that; else use UTC as ultra-fallback
    rules = ch.rules_json or {}
    scope = ((rules.get("time_window") or {}).get("scope")) or "participant_local"
    ch_tz = ((rules.get("time_window") or {}).get("timezone"))
    if not tz:
        tz = ch_tz if scope == "challenge_tz" and ch_tz else "UTC"

    # Prevent duplicate membership
    existing = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
    if existing:
        # Optional: update timezone if provided (allow timezone updates)
        if tz:
            existing.timezone = tz
            await session.commit()
            await session.refresh(existing)
        return ParticipantPublic(
            id=existing.id, 
            challenge_id=existing.challenge_id, 
            user_id=existing.user_id, 
            joined_at=existing.joined_at,
            timezone=existing.timezone
        )

    p = Participant(challenge_id=ch.id, user_id=user.id, timezone=tz)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return ParticipantPublic(
        id=p.id, 
        challenge_id=p.challenge_id, 
        user_id=p.user_id, 
        joined_at=p.joined_at,
        timezone=p.timezone
    )