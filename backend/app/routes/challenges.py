from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, exists
from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.models.user import User
from app.models.submission import Submission
from app.schemas.challenge import ChallengeCreate, ChallengePublic, ParticipantPublic, RulesDSL, ParticipantWithUser
from app.schemas.submission import SubmissionPublic, LeaderboardRow
from app.services.invite_code import generate_code
from app.services.media import analyze_image, ext_for_mime
from app.services.storage import put_bytes, get_bytes, presign_get
from app.config import settings
from app.services.slots import compute_slot
from app.services.wallet import debit_tokens, InsufficientFunds
from app.services.overlay import overlay_code
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone as dt_tz, timedelta
from zoneinfo import ZoneInfo
import uuid
from rq import Queue
from redis import Redis
from app.jobs.verify_submission import verify_submission
import os
from app.models.ledger import Ledger
from app.services.ledger import ensure_stake_entry

router = APIRouter(prefix="/challenges", tags=["challenges"])

# RQ queue (lazy single instance)
_redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
q = Queue("default", connection=_redis)

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
    # Generate presigned URL for image if available
    image_url = None
    has_image = bool(ch.image_storage_key)
    if has_image:
        try:
            image_url = presign_get(ch.image_storage_key)
        except Exception:
            # If presigning fails, still mark has_image as True but no URL
            pass
    
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
        image_url=image_url,
        has_image=has_image,
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
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    x_client_tz: str | None = Header(default=None, alias="X-Client-Timezone"),
    payload: str = Body(..., description="JSON string of challenge data"),
    image: UploadFile | None = File(default=None, description="Optional challenge image"),
):
    # Parse the JSON payload
    try:
        import json
        payload_dict = json.loads(payload)
        challenge_data = ChallengeCreate.model_validate(payload_dict)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON in payload")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid challenge data: {str(e)}")
    
    if challenge_data.ends_at <= challenge_data.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")
    # Generate a unique invite code (retry on collision)
    for _ in range(5):
        code = generate_code()
        ch = Challenge(
            owner_id=user.id,
            name=challenge_data.name,
            description=challenge_data.description,
            visibility=challenge_data.visibility,
            invite_code=code,
            starts_at=challenge_data.starts_at,
            ends_at=challenge_data.ends_at,
            entry_stake_tokens=challenge_data.entry_stake_tokens,
            rules_json=challenge_data.rules.model_dump(mode='json'),
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

            await session.flush()
            # Stake for owner (if any)
            owner_part = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
            
            # Stake (wallet -> challenge)
            stake_amt = int(ch.entry_stake_tokens or 0)
            if stake_amt > 0:
                try:
                    await debit_tokens(
                        session,
                        user_id=user.id,
                        tokens=stake_amt,
                        external_id=f"stake_{str(ch.id)[-8:]}_{str(owner_part.id)[-8:]}",
                        note="stake_join_owner",
                    )
                except InsufficientFunds:
                    await session.rollback()
                    raise HTTPException(status_code=402, detail="Insufficient wallet balance for stake")
                    
            # Ledger STAKE (idempotent via unique partial index)
            await ensure_stake_entry(session, ch, owner_part)
            
            # Process challenge image if provided
            if image:
                try:
                    data = await image.read()
                    mime, _, _ = analyze_image(data)  # validates JPEG/PNG and integrity
                    
                    # Store to S3 (MinIO) using existing path structure
                    ext = ext_for_mime(mime)
                    storage_key = f"ch/{ch.id}/challenge_image.{ext}"
                    put_bytes(storage_key, data, mime)
                    
                    # Update challenge with image info
                    ch.image_storage_key = storage_key
                    ch.image_mime_type = mime
                except Exception as e:
                    await session.rollback()
                    raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")
            
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

    # Create participant and stake atomically
    p = Participant(challenge_id=ch.id, user_id=user.id, timezone=tz)
    session.add(p)
    await session.flush()
    
    # Stake (wallet -> challenge)
    stake_amt = int(ch.entry_stake_tokens or 0)
    if stake_amt > 0:
        try:
            await debit_tokens(
                session,
                user_id=user.id,
                tokens=stake_amt,
                external_id=f"stake_{str(ch.id)[-8:]}_{str(p.id)[-8:]}",
                note="stake_join",
            )
        except InsufficientFunds:
            await session.rollback()
            raise HTTPException(status_code=402, detail="Insufficient wallet balance for stake")
            
    # Ledger STAKE (idempotent via unique partial index)
    await ensure_stake_entry(session, ch, p)
    await session.commit()
    await session.refresh(p)
    return ParticipantPublic(
        id=p.id,
        challenge_id=p.challenge_id, 
        user_id=p.user_id, 
        joined_at=p.joined_at,
        timezone=p.timezone
    )

@router.get("/{challenge_id}/watermark-code")
async def get_watermark_code(
    challenge_id: str,
    slot_key: str = Query(..., description="The slot key (e.g., '2025-01-15') to generate code for"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """
    Generate a watermark code for the mobile app to embed in photos.
    The code is deterministic based on (challenge_id, participant_id, slot_key).
    """
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Must be a participant
    participant = await session.scalar(
        select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id)
    )
    if not participant:
        raise HTTPException(status_code=403, detail="Not a participant")

    # Generate the code
    code = overlay_code(str(ch.id), str(participant.id), slot_key)
    
    return {
        "challenge_id": challenge_id,
        "participant_id": str(participant.id),
        "slot_key": slot_key,
        "code": code,
        "watermark_text": f"CHALLY_{code}",
        "full_string": f"CHALLY_WATERMARK:CHALLY_{code}:SUBMISSION:{challenge_id}:{participant.id}:{slot_key}",
    }


def _to_submission_public(s: Submission) -> SubmissionPublic:
    media = f"/challenges/{s.challenge_id}/submissions/{s.id}/image" if s.storage_key else None
    return SubmissionPublic(
        id=s.id,
        challenge_id=s.challenge_id,
        participant_id=s.participant_id,
        slot_key=s.slot_key,
        window_start_utc=s.window_start_utc,
        window_end_utc=s.window_end_utc,
        submitted_at=s.submitted_at,
        proof_type=s.proof_type,
        status=s.status,
        text_content=s.text_content,
        mime_type=s.mime_type,
        media_url=media,
        meta=s.meta_json or {},
    )

# --- NEW: submit proof ---
@router.post("/{challenge_id}/submit", response_model=SubmissionPublic, status_code=201)
async def submit_proof(
    challenge_id: str,
    proof_type: str = Query(..., description="one of allowed rules proof_types"),
    text: str | None = Query(default=None, description="text content when proof_type='text'"),
    overlay_code: str | None = Query(default=None, description="typed overlay code if required"),
    submission_stage: str | None = Query(default=None, description="optional stage: start/ongoing/end"),
    file: UploadFile | None = File(default=None, description="image file when proof_type is an image"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Status gate: allow only when active and runtime=started
    now = datetime.now(dt_tz.utc)
    runtime = compute_runtime_state(ch, now)
    if ch.status not in ("active",) or runtime not in ("started",):
        raise HTTPException(status_code=400, detail=f"Submissions closed (status={ch.status}, runtime={runtime})")

    # Participant check
    participant = await session.scalar(
        select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id)
    )
    if not participant:
        raise HTTPException(status_code=403, detail="You are not a participant of this challenge")

    rules = RulesDSL.model_validate(ch.rules_json)
    if proof_type not in rules.proof_types:
        raise HTTPException(status_code=400, detail="Proof type not allowed for this challenge")

    # Compute current slot & window
    scope = rules.time_window.scope or "participant_local"
    ch_tz = rules.time_window.timezone
    slot_info = compute_slot(
        now_utc=now,
        frequency=rules.frequency,
        start_t=rules.time_window.start,
        end_t=rules.time_window.end,
        scope=scope,
        participant_tz=participant.timezone,
        challenge_tz=ch_tz,
        custom_days=rules.custom_days,
    )
    if not slot_info:
        if rules.frequency == "custom" and rules.custom_days:
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            allowed_days = ", ".join(day_names[d] for d in sorted(rules.custom_days))
            raise HTTPException(status_code=400, detail=f"Submissions only allowed on: {allowed_days}")
        raise HTTPException(status_code=400, detail="Not within a valid submission window")

    slot_key, win_start, win_end = slot_info

    # NEW: Query existing submissions for this slot (to support multiple submissions per slot)
    existing_submissions = (
        await session.execute(
            select(Submission)
            .where(
                Submission.participant_id == participant.id,
                Submission.slot_key == slot_key
            )
            .order_by(Submission.submitted_at.asc())
        )
    ).scalars().all()
    
    existing_count = len(existing_submissions)

    # NEW: Check max submissions per slot
    if existing_count >= rules.max_submissions_per_slot:
        raise HTTPException(
            status_code=409,
            detail=f"Already submitted {existing_count}/{rules.max_submissions_per_slot} times for this slot"
        )

    # NEW: Check submission interval (time between submissions)
    if rules.submission_interval_minutes and existing_submissions:
        last_submission = existing_submissions[-1]
        time_since_last = (now - last_submission.submitted_at).total_seconds() / 60
        
        if time_since_last < rules.submission_interval_minutes:
            minutes_remaining = int(rules.submission_interval_minutes - time_since_last)
            raise HTTPException(
                status_code=429,  # Too Many Requests
                detail=f"Must wait {minutes_remaining} more minute(s) before next submission"
            )

    # NEW: Validate submission stages (if required)
    if rules.require_submission_stages:
        if not submission_stage:
            raise HTTPException(
                status_code=400,
                detail=f"Submission stage required. Must be one of: {rules.submission_stages}"
            )
        
        if rules.submission_stages and submission_stage not in rules.submission_stages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid stage '{submission_stage}'. Must be one of: {rules.submission_stages}"
            )
        
        # Check if this stage already exists
        stage_exists = any(s.submission_stage == submission_stage for s in existing_submissions)
        if stage_exists:
            raise HTTPException(
                status_code=409,
                detail=f"Already submitted '{submission_stage}' stage for this slot"
            )
        
        # Enforce stage order
        if rules.submission_stages:
            expected_stage_index = existing_count
            if expected_stage_index < len(rules.submission_stages):
                expected_stage = rules.submission_stages[expected_stage_index]
                if submission_stage != expected_stage:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Must submit stages in order. Expected: '{expected_stage}', got: '{submission_stage}'"
                    )

    # Process content
    text_content = None
    storage_key = None
    mime_type = None
    meta = {}

    # ... after we build meta for image/text
    meta = {}
    # if text proof
    if proof_type == "text":
        if not text:
            raise HTTPException(status_code=400, detail="Missing text content")
        text_content = text.strip()
        if not text_content:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        meta = {}
    else:
        if not file:
            raise HTTPException(status_code=400, detail="Missing image file")
        data = await file.read()
        mime, phash_hex, exif = analyze_image(data)  # validates JPEG/PNG and integrity
        mime_type = mime
        meta = {"phash": phash_hex, "exif": exif or {}}
        
        # Store original image to S3 (MinIO, speaks S3 API)  
        # Watermarking will be done by worker job
        ext = ext_for_mime(mime)
        storage_key = f"ch/{ch.id}/p/{participant.id}/{slot_key}/{uuid.uuid4().hex}.{ext}"
        put_bytes(storage_key, data, mime_type)

    # record typed overlay (if any)
    if overlay_code:
        meta["overlay_typed"] = overlay_code.strip().upper()

    # Create submission (initially pending; job decides accept/reject)
    sub = Submission(
        challenge_id=ch.id,
        participant_id=participant.id,
        slot_key=slot_key,
        window_start_utc=win_start,
        window_end_utc=win_end,
        proof_type=proof_type,
        status="pending",
        submission_sequence=existing_count + 1,  # NEW: Track submission order
        submission_stage=submission_stage,  # NEW: Track submission stage
        text_content=text_content,
        storage_key=storage_key,
        mime_type=mime_type,
        storage_keys=[storage_key] if storage_key else [],  # NEW: Array support
        mime_types=[mime_type] if mime_type else [],  # NEW: Array support
        meta_json=meta,
    )
    session.add(sub)
    await session.commit()
    await session.refresh(sub)

    # Enqueue verification directly (no server-side watermarking)
    try:
        q.enqueue(verify_submission, str(sub.id), job_timeout=60)
    except Exception:
        # Non-fatal in dev; submission stays pending
        pass

    return _to_submission_public(sub)

# --- NEW: list submissions (owner sees all; participant can pass mine=1) ---
@router.get("/{challenge_id}/submissions", response_model=list[SubmissionPublic])
async def list_submissions(
    challenge_id: str,
    mine: int = Query(default=0, ge=0, le=1),
    day: str | None = Query(default=None, description="YYYY-MM-DD or 'today'"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Must be participant to view; owners can view all
    viewer_is_owner = (ch.owner_id == user.id)
    part = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
    if not (viewer_is_owner or part):
        raise HTTPException(status_code=403, detail="Not a participant")

    q = select(Submission).where(Submission.challenge_id == ch.id)

    # Filter mine if requested
    if mine == 1:
        if not part:
            raise HTTPException(status_code=400, detail="You are not a participant")
        q = q.where(Submission.participant_id == part.id)

    # Optional day filter by slot_key
    if day:
        if day == "today":
            # Resolve today's slot key for the viewer (use viewer's tz for anchor)
            rules = RulesDSL.model_validate(ch.rules_json)
            scope = rules.time_window.scope or "participant_local"
            tz_name = (part.timezone if part else "UTC") if scope == "participant_local" else (rules.time_window.timezone or "UTC")
            local_today = datetime.now(dt_tz.utc).astimezone(ZoneInfo(tz_name)).date().isoformat()
            q = q.where(Submission.slot_key == local_today)
        else:
            q = q.where(Submission.slot_key == day)

    q = q.order_by(Submission.submitted_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return [_to_submission_public(s) for s in rows]

# --- NEW: leaderboard ---
@router.get("/{challenge_id}/leaderboard", response_model=list[LeaderboardRow])
async def leaderboard(
    challenge_id: str,
    period: str = Query(default="total", pattern="^(total|current_week)$"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    ch = await session.get(Challenge, challenge_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Any participant can view
    viewer_part = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
    if not (viewer_part or user.id == ch.owner_id):
        raise HTTPException(status_code=403, detail="Not a participant")

    # Count accepted-ish submissions per user
    base = (
        select(User.id, User.username, func.count(Submission.id))
        .join(Participant, Participant.user_id == User.id)
        .join(Submission, Submission.participant_id == Participant.id)
        .where(Participant.challenge_id == ch.id)
        .where(Submission.status.in_(("accepted", "flagged", "pending")))
        .group_by(User.id, User.username)
    )

    if period == "current_week":
        # Use UTC week bounds for simplicity (good enough for M3)
        now = datetime.now(dt_tz.utc)
        monday = now - timedelta(days=now.weekday())
        monday_utc = datetime(monday.year, monday.month, monday.day, tzinfo=dt_tz.utc)
        next_monday_utc = monday_utc + timedelta(days=7)
        base = base.where(Submission.submitted_at >= monday_utc, Submission.submitted_at < next_monday_utc)

    rows = (await session.execute(base.order_by(func.count(Submission.id).desc()))).all()

    # submitted_today flag per user
    today_counts = {}
    now = datetime.now(dt_tz.utc)
    # Check today existence by slot_key == viewer's "today" to keep semantics simple
    rules = RulesDSL.model_validate(ch.rules_json)
    scope = rules.time_window.scope or "participant_local"
    # We'll compute using each participant's own timezone by joining again (cheap enough)
    for (uid, uname, total) in rows:
        p = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == uid))
        tz_name = p.timezone if p else "UTC"
        local_today = now.astimezone(ZoneInfo(tz_name if scope == "participant_local" else (rules.time_window.timezone or "UTC"))).date().isoformat()
        exists_today = await session.scalar(
            select(func.count(Submission.id))
            .join(Participant, Participant.id == Submission.participant_id)
            .where(Participant.user_id == uid, Participant.challenge_id == ch.id, Submission.slot_key == local_today)
        )
        today_counts[uid] = (exists_today or 0) > 0

    return [
        LeaderboardRow(user_id=uid, username=uname, total=int(total), submitted_today=bool(today_counts.get(uid, False)))
        for (uid, uname, total) in rows
    ]

@router.get("/{challenge_id}/submissions/{submission_id}/image")
async def get_submission_image(
    challenge_id: str,
    submission_id: str,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Retrieve the uploaded image for a submission."""
    # Check if user is a participant in the challenge
    participant = await session.scalar(
        select(Participant).where(Participant.challenge_id == challenge_id, Participant.user_id == user.id)
    )
    if not participant:
        raise HTTPException(status_code=403, detail="You are not a participant of this challenge")
    
    # Get the submission
    submission = await session.scalar(
        select(Submission).where(Submission.id == submission_id, Submission.challenge_id == challenge_id)
    )
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if not submission.storage_key:
        raise HTTPException(status_code=404, detail="No image associated with this submission")
    
    try:
        data, content_type = get_bytes(submission.storage_key)
        from fastapi.responses import Response
        return Response(content=data, media_type=content_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image file not found in storage")

@router.get("/{challenge_id}/image")
async def get_challenge_image(
    challenge_id: str,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Retrieve the challenge image."""
    # Get the challenge
    challenge = await session.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    
    # Check if challenge has an image
    if not challenge.image_storage_key:
        raise HTTPException(status_code=404, detail="No image associated with this challenge")
    
    try:
        data, content_type = get_bytes(challenge.image_storage_key)
        from fastapi.responses import Response
        return Response(content=data, media_type=content_type)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Image file not found in storage")

