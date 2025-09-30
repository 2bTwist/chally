from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone as dt_tz
from zoneinfo import ZoneInfo

from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.models.submission import Submission
from app.schemas.submission import FeedItem, SubmissionPublic
from app.schemas.challenge import RulesDSL
from app.config import settings
from app.services.storage import presign_get

router = APIRouter(prefix="/feed", tags=["feed"])

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

@router.get("/today", response_model=list[FeedItem])
async def my_today_feed(session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    # All challenges I joined (incl. ones I own because owner auto-joins)
    parts = (await session.execute(select(Participant).where(Participant.user_id == user.id))).scalars().all()
    if not parts:
        return []

    out: list[FeedItem] = []
    now = datetime.now(dt_tz.utc)

    for p in parts:
        ch = await session.get(Challenge, p.challenge_id)
        if not ch:
            continue

        rules = RulesDSL.model_validate(ch.rules_json)
        scope = rules.time_window.scope or "participant_local"
        tz_name = p.timezone if scope == "participant_local" else (rules.time_window.timezone or "UTC")
        local_today = now.astimezone(ZoneInfo(tz_name)).date().isoformat()

        my_sub = await session.scalar(
            select(Submission).where(Submission.participant_id == p.id, Submission.slot_key == local_today)
        )
        out.append(
            FeedItem(
                challenge_id=ch.id,
                challenge_name=ch.name,
                submitted_today=bool(my_sub),
                my_submission=_to_submission_public(my_sub) if my_sub else None,
            )
        )

    return out