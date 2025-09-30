from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from math import ceil

from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.models.submission import Submission
from app.models.review import Vote
from app.schemas.challenge import RulesDSL
from app.schemas.review import VoteCreate
from app.schemas.submission import SubmissionPublic

router = APIRouter(prefix="/reviews", tags=["reviews"])

def _pub(ch_id, s: Submission) -> SubmissionPublic:
    media = f"/challenges/{ch_id}/submissions/{s.id}/image" if s.storage_key else None
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

@router.get("", response_model=list[SubmissionPublic])
async def list_pending(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    challenge_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    # All challenges where user participates
    q_parts = select(Participant).where(Participant.user_id == user.id)
    parts = (await session.execute(q_parts)).scalars().all()
    if not parts:
        return []

    part_by_ch = {p.challenge_id: p for p in parts}
    part_ids = [p.id for p in parts]

    q = select(Submission).where(Submission.status == "pending")
    if challenge_id:
        if challenge_id not in part_by_ch:
            raise HTTPException(status_code=403, detail="Not a participant in that challenge")
        q = q.where(Submission.challenge_id == challenge_id)

    # exclude my own submissions
    q = q.where(~Submission.participant_id.in_(part_ids)).order_by(Submission.submitted_at.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [_pub(s.challenge_id, s) for s in rows]

@router.post("/vote")
async def cast_vote(payload: VoteCreate, session: AsyncSession = Depends(get_session), user=Depends(get_current_user)):
    s = await session.get(Submission, payload.submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="Submission not found")
    ch = await session.get(Challenge, s.challenge_id)
    viewer = await session.scalar(select(Participant).where(Participant.challenge_id == ch.id, Participant.user_id == user.id))
    if not viewer:
        raise HTTPException(status_code=403, detail="Not a participant")
    if viewer.id == s.participant_id:
        raise HTTPException(status_code=400, detail="Cannot vote on your own submission")
    if s.status != "pending":
        raise HTTPException(status_code=400, detail="Submission not pending review")

    # Upsert-like guard (unique constraint handles race)
    v = Vote(submission_id=s.id, voter_participant_id=viewer.id, approve=payload.approve)
    session.add(v)
    await session.flush()

    # Quorum evaluation
    rules = RulesDSL.model_validate(ch.rules_json)
    quorum_pct = max(50, min(100, rules.verification.quorum_pct))
    # Eligible = participants minus the submitter
    eligible_cnt = await session.scalar(
        select(func.count()).select_from(Participant).where(Participant.challenge_id == ch.id)
    )
    eligible = max(0, int(eligible_cnt or 0) - 1)

    # If nobody else to vote, auto-accept
    if eligible <= 0:
        s.status = "accepted"
        await session.commit()
        return {"status": s.status, "reason": "no_eligible_reviewers"}

    # Count votes so far
    votes = (await session.execute(
        select(Vote).where(Vote.submission_id == s.id)
    )).scalars().all()
    approvals = sum(1 for x in votes if x.approve)
    rejections = sum(1 for x in votes if not x.approve)

    needed = ceil(quorum_pct * eligible / 100.0)

    if approvals >= needed:
        s.status = "accepted"
    elif rejections > (eligible - needed):
        s.status = "rejected"
    # else keep pending

    await session.commit()
    return {"status": s.status, "approvals": approvals, "rejections": rejections, "needed": needed, "eligible": eligible}