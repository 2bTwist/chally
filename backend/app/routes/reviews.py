from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from math import ceil
from datetime import datetime, timezone as dt_tz, timedelta

from app.db import get_session
from app.auth_deps import get_current_user
from app.models.challenge import Challenge, Participant
from app.models.submission import Submission
from app.models.review import Vote
from app.schemas.challenge import RulesDSL
from app.schemas.review import VoteCreate
from app.schemas.submission import SubmissionPublic
from app.services.ledger import create_penalty_once

router = APIRouter(prefix="/reviews", tags=["reviews"])

StatusFilter = Literal["pending", "accepted", "rejected", "all"]

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

async def _list_for_user(
    session: AsyncSession,
    user,
    status: StatusFilter,
    challenge_id: UUID | None,
    mine: int,
    limit: int,
):
    # All challenges where user participates
    parts = (await session.execute(select(Participant).where(Participant.user_id == user.id))).scalars().all()
    if not parts:
        return []
    part_by_ch = {p.challenge_id: p for p in parts}
    my_part_ids = [p.id for p in parts]
    ch_ids = list(part_by_ch.keys())

    q = select(Submission).where(Submission.challenge_id.in_(ch_ids))

    if challenge_id:
        if challenge_id not in part_by_ch:
            raise HTTPException(status_code=403, detail="Not a participant in that challenge")
        q = q.where(Submission.challenge_id == challenge_id)

    if status != "all":
        q = q.where(Submission.status == status)

    # Default behavior:
    # - pending: show reviewable items (exclude my own)
    # - others: show all unless mine=1
    if status == "pending":
        if mine == 1:
            # my pending items (awaiting quorum)
            q = q.where(Submission.participant_id.in_(my_part_ids))
        else:
            q = q.where(~Submission.participant_id.in_(my_part_ids))
    else:
        if mine == 1:
            q = q.where(Submission.participant_id.in_(my_part_ids))

    q = q.order_by(Submission.submitted_at.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [_pub(s.challenge_id, s) for s in rows]

@router.get("", response_model=list[SubmissionPublic])
async def list_default(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    challenge_id: UUID | None = Query(default=None),
    mine: int = Query(default=0, ge=0, le=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    # Back-compat: defaults to pending queue
    return await _list_for_user(session, user, "pending", challenge_id, mine, limit)

@router.get("/stats")
async def review_stats(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    challenge_id: UUID | None = Query(default=None),
):
    """
    Returns global + per-challenge counts:
      - pending_to_review: pending items you can still vote on
      - mine_pending: your submissions waiting for quorum
      - accepted_today / rejected_today: activity pulse (UTC day)
      - my_votes_today: how many votes you cast today (global)
    """
    parts = (await session.execute(select(Participant).where(Participant.user_id == user.id))).scalars().all()
    if not parts:
        return {
            "global": {"pending_to_review": 0, "mine_pending": 0, "accepted_today": 0, "rejected_today": 0, "my_votes_today": 0},
            "per_challenge": [],
        }

    part_by_ch = {p.challenge_id: p for p in parts}
    ch_ids = list(part_by_ch.keys())
    if challenge_id:
        if challenge_id not in part_by_ch:
            raise HTTPException(status_code=403, detail="Not a participant in that challenge")
        ch_ids = [challenge_id]

    # UTC day bounds
    now = datetime.now(dt_tz.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=dt_tz.utc)
    day_end = day_start + timedelta(days=1)

    per = []
    g_pending = g_mine_pending = g_acc = g_rej = 0

    # Global votes today
    my_part_ids = [p.id for p in parts]
    my_votes_today = await session.scalar(
        select(func.count()).select_from(Vote)
        .where(Vote.voter_participant_id.in_(my_part_ids))
        .where(Vote.created_at >= day_start, Vote.created_at < day_end)
    ) or 0

    # Preload challenge names
    ch_map = {c.id: c for c in (await session.execute(select(Challenge).where(Challenge.id.in_(ch_ids)))).scalars().all()}

    for cid in ch_ids:
        me_p = part_by_ch[cid]

        # Subquery: ids I already voted on in this challenge
        voted_ids_subq = select(Vote.submission_id).where(Vote.voter_participant_id == me_p.id).subquery()

        pending_to_review = await session.scalar(
            select(func.count()).select_from(Submission)
            .where(Submission.challenge_id == cid)
            .where(Submission.status == "pending")
            .where(Submission.participant_id != me_p.id)
            .where(~Submission.id.in_(voted_ids_subq))
        ) or 0

        mine_pending = await session.scalar(
            select(func.count()).select_from(Submission)
            .where(Submission.challenge_id == cid)
            .where(Submission.status == "pending")
            .where(Submission.participant_id == me_p.id)
        ) or 0

        accepted_today = await session.scalar(
            select(func.count()).select_from(Submission)
            .where(Submission.challenge_id == cid)
            .where(Submission.status == "accepted")
            .where(Submission.submitted_at >= day_start, Submission.submitted_at < day_end)
        ) or 0

        rejected_today = await session.scalar(
            select(func.count()).select_from(Submission)
            .where(Submission.challenge_id == cid)
            .where(Submission.status == "rejected")
            .where(Submission.submitted_at >= day_start, Submission.submitted_at < day_end)
        ) or 0

        per.append({
            "challenge_id": str(cid),
            "challenge_name": ch_map.get(cid).name if cid in ch_map else "",
            "pending_to_review": int(pending_to_review),
            "mine_pending": int(mine_pending),
            "accepted_today": int(accepted_today),
            "rejected_today": int(rejected_today),
        })

        g_pending += int(pending_to_review)
        g_mine_pending += int(mine_pending)
        g_acc += int(accepted_today)
        g_rej += int(rejected_today)

    return {
        "global": {
            "pending_to_review": g_pending,
            "mine_pending": g_mine_pending,
            "accepted_today": g_acc,
            "rejected_today": g_rej,
            "my_votes_today": int(my_votes_today),
        },
        "per_challenge": per,
    }

@router.get("/{status}", response_model=list[SubmissionPublic])
async def list_with_status(
    status: StatusFilter = Path(..., regex="^(pending|accepted|rejected|all)$"),
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
    challenge_id: UUID | None = Query(default=None),
    mine: int = Query(default=0, ge=0, le=1, description="1=only my submissions"),
    limit: int = Query(default=20, ge=1, le=100),
):
    return await _list_for_user(session, user, status, challenge_id, mine, limit)

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

    # Wrap vote, quorum evaluation, and penalty creation in explicit transaction
    async with session.begin():
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
            return {"status": s.status, "reason": "no_eligible_reviewers"}

        # Count votes so far
        votes = (await session.execute(
            select(Vote).where(Vote.submission_id == s.id)
        )).scalars().all()
        approvals = sum(1 for x in votes if x.approve)
        rejections = sum(1 for x in votes if not x.approve)

        needed = ceil(quorum_pct * eligible / 100.0)

        prev_status = s.status
        if approvals >= needed:
            s.status = "accepted"
        elif rejections > (eligible - needed):
            s.status = "rejected"
        # else keep pending

        # Apply penalty exactly once when a submission becomes rejected
        if prev_status != "rejected" and s.status == "rejected":
            penalty = int(rules.penalties or 0)
            if penalty > 0:
                await create_penalty_once(session, ch.id, s.participant_id, s.id, penalty)
    return {"status": s.status, "approvals": approvals, "rejections": rejections, "needed": needed, "eligible": eligible}