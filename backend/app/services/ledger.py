from __future__ import annotations
from typing import Iterable, Tuple
from uuid import UUID
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import Ledger
from app.models.challenge import Challenge, Participant
from app.models.submission import Submission
from app.models.user import User
from app.schemas.challenge import RulesDSL
from app.services.wallet import credit_tokens

# ---------- helpers: stakes / penalties ----------

async def ensure_stake_entry(session: AsyncSession, ch: Challenge, p: Participant) -> None:
    """Create a single STAKE entry for this participant if needed."""
    amt = int(ch.entry_stake_tokens or 0)
    if amt <= 0:
        return
    exists = await session.scalar(
        select(Ledger).where(
            Ledger.challenge_id == ch.id,
            Ledger.participant_id == p.id,
            Ledger.type == "STAKE",
        )
    )
    if exists:
        return
    session.add(Ledger(challenge_id=ch.id, participant_id=p.id, type="STAKE", amount=-amt, note="entry_stake"))


async def create_penalty_once(session: AsyncSession, ch_id: UUID, participant_id: UUID, submission_id: UUID, penalty_tokens: int) -> None:
    """Idempotent penalty per submission with race condition handling via PostgreSQL ON CONFLICT."""
    from sqlalchemy import text
    if penalty_tokens <= 0:
        return
    
    # Use PostgreSQL's ON CONFLICT to handle race conditions atomically
    await session.execute(text("""
        INSERT INTO ledger (id, challenge_id, participant_id, type, amount, ref_submission_id, note, created_at)
        VALUES (gen_random_uuid(), :ch_id, :participant_id, 'PENALTY', :amount, :submission_id, 'rejected_submission', NOW())
        ON CONFLICT (participant_id, type, ref_submission_id) DO NOTHING
    """), {
        "ch_id": ch_id,
        "participant_id": participant_id,
        "amount": -int(penalty_tokens),
        "submission_id": submission_id,
    })

# ---------- compute: balances & pool ----------

async def snapshot_for_challenge(session: AsyncSession, challenge_id: UUID, viewer_user_id: UUID) -> dict:
    """Return balances, pool, entries, and viewer balance."""
    # Entries
    entries = (await session.execute(
        select(Ledger).where(Ledger.challenge_id == challenge_id).order_by(Ledger.created_at.asc())
    )).scalars().all()

    # Participant -> user mapping and usernames
    parts = (await session.execute(
        select(Participant, User.id, User.username)
        .join(User, User.id == Participant.user_id)
        .where(Participant.challenge_id == challenge_id)
    )).all()
    by_part: dict[UUID, tuple[UUID, str]] = {p.id: (uid, uname) for (p, uid, uname) in parts}

    # Compute per-participant balances & pool
    balances: dict[UUID, int] = {}
    total_sum = 0
    for e in entries:
        balances[e.participant_id] = balances.get(e.participant_id, 0) + int(e.amount)
        total_sum += int(e.amount)

    pool = max(0, -total_sum)

    # viewer balance
    viewer_part = await session.scalar(
        select(Participant).where(Participant.challenge_id == challenge_id, Participant.user_id == viewer_user_id)
    )
    your_balance = balances.get(viewer_part.id, 0) if viewer_part else 0

    # shape output
    from app.schemas.ledger import LedgerEntryPublic, ParticipantBalance
    # Filter out platform revenue entries from participant totals
    from uuid import UUID
    platform_id = UUID("00000000-0000-0000-0000-000000000000")
    participant_balances = [
        ParticipantBalance(
            participant_id=pid,
            user_id=by_part.get(pid, (None, ""))[0],
            username=by_part.get(pid, (None, ""))[1] or "",
            balance=int(bal)
        ) for pid, bal in sorted(balances.items(), key=lambda kv: (-kv[1], str(kv[0])))
        if pid != platform_id  # Exclude platform pseudo-participant
    ]
    
    return {
        "pool_tokens": int(pool),
        "your_balance": int(your_balance),
        "totals": participant_balances,
        "entries": [
            LedgerEntryPublic(
                id=e.id,
                challenge_id=e.challenge_id,
                participant_id=e.participant_id,
                type=e.type,
                amount=int(e.amount),
                ref_submission_id=e.ref_submission_id,
                note=e.note,
                created_at=e.created_at,
            ) for e in entries
        ]
    }

# ---------- finishers & payout ----------

def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())

def _date_range_inclusive(a: date, b: date) -> Iterable[date]:
    cur = a
    step = timedelta(days=1)
    while cur <= b:
        yield cur
        cur += step

def _expected_slots_count(ch: Challenge, p: Participant, rules: RulesDSL) -> Tuple[int, str, str]:
    """
    Return (expected_count, key_min, key_max) using slot_key semantics.
    - For daily/weekdays: slot_key = local YYYY-MM-DD
    - For weekly:          slot_key = Monday anchor YYYY-MM-DD
    """
    tz_name = p.timezone if (rules.time_window.scope or "participant_local") == "participant_local" else (rules.time_window.timezone or "UTC")
    tz = ZoneInfo(tz_name)

    start_local = ch.starts_at.astimezone(tz).date()
    end_local = ch.ends_at.astimezone(tz).date()
    if start_local > end_local:
        return 0, start_local.isoformat(), end_local.isoformat()

    freq = rules.frequency

    if freq == "weekly":
        first = _monday_of(start_local)
        last = _monday_of(end_local)
        weeks = ((last - first).days // 7) + 1
        return weeks, first.isoformat(), last.isoformat()

    # daily / weekdays
    cnt = 0
    for d in _date_range_inclusive(start_local, end_local):
        if freq == "weekdays" and d.weekday() >= 5:
            continue
        cnt += 1
    return cnt, start_local.isoformat(), end_local.isoformat()


async def determine_finishers(session: AsyncSession, ch: Challenge, rules: RulesDSL) -> list[Participant]:
    """Finishers = accepted_count >= expected_count - grace."""
    participants = (await session.execute(
        select(Participant).where(Participant.challenge_id == ch.id)
    )).scalars().all()

    finishers: list[Participant] = []
    grace = int(rules.grace or 0)

    for p in participants:
        expected, key_min, key_max = _expected_slots_count(ch, p, rules)
        if expected <= 0:
            continue
        # Count distinct accepted slot_keys within range
        accepted = await session.scalar(
            select(func.count(func.distinct(Submission.slot_key)))
            .where(
                Submission.participant_id == p.id,
                Submission.status == "accepted",
                Submission.slot_key >= key_min,
                Submission.slot_key <= key_max,
            )
        ) or 0
        if int(accepted) >= max(0, expected - grace):
            finishers.append(p)

    return finishers


async def close_and_payout(session: AsyncSession, ch: Challenge) -> dict:
    """
    Idempotent close:
      - If already ended or PAYOUT exists => no-op
      - Else compute pool and finishers, split equally, distribute remainder deterministically.
    """
    # If any payout already exists, consider closed
    existing_payout = await session.scalar(
        select(func.count()).select_from(Ledger).where(Ledger.challenge_id == ch.id, Ledger.type == "PAYOUT")
    )
    if ch.status == "ended" or (existing_payout and int(existing_payout) > 0):
        # Return a snapshot anyway
        snap = await snapshot_for_challenge(session, ch.id, ch.owner_id)
        return {"status": "already_ended", **snap}

    rules = RulesDSL.model_validate(ch.rules_json)
    finishers = await determine_finishers(session, ch, rules)

    # Current pool
    total_sum = await session.scalar(
        select(func.coalesce(func.sum(Ledger.amount), 0)).where(Ledger.challenge_id == ch.id)
    )
    pool = max(0, -int(total_sum or 0))

    if pool <= 0 or not finishers:
        ch.status = "ended"
        
        # NEW: Capture forfeited stakes as platform revenue
        if pool > 0:
            # All stakes are forfeited - create a PLATFORM_REVENUE entry
            # Using a special UUID for platform revenue tracking
            from uuid import UUID
            platform_id = UUID("00000000-0000-0000-0000-000000000000")  # Platform pseudo-participant
            session.add(Ledger(
                challenge_id=ch.id, 
                participant_id=platform_id,  # Special platform ID
                type="PLATFORM_REVENUE", 
                amount=pool,  # Positive amount (platform gains the forfeited stakes)
                note=f"forfeited_stakes_{len(finishers)}_finishers"
            ))
        
        await session.flush()
        snap = await snapshot_for_challenge(session, ch.id, ch.owner_id)
        return {"status": "ended_no_payout", "finishers": len(finishers), "platform_revenue": pool, **snap}

    n = len(finishers)
    per, rem = divmod(pool, n)

    # Map participant -> user_id once
    part_to_user = {p.id: uid for (p, uid, _uname) in (
        await session.execute(
            select(Participant, User.id, User.username)
            .join(User, User.id == Participant.user_id)
            .where(Participant.challenge_id == ch.id)
        )
    ).all()}

    # deterministic remainder distribution by increasing participant UUID
    sorted_parts = sorted(finishers, key=lambda x: str(x.id))
    for idx, p in enumerate(sorted_parts):
        amt = per + (1 if idx < rem else 0)
        if amt > 0:
            session.add(Ledger(challenge_id=ch.id, participant_id=p.id, type="PAYOUT", amount=amt, note="challenge_payout"))
            # Also credit user wallet (idempotent by external_id)
            uid = part_to_user.get(p.id)
            if uid:
                await credit_tokens(
                    session,
                    user_id=uid,
                    tokens=amt,
                    external_id=f"payout_{str(ch.id)[-8:]}_{str(p.id)[-8:]}",
                    note="challenge_payout",
                )

    ch.status = "ended"
    await session.flush()

    snap = await snapshot_for_challenge(session, ch.id, ch.owner_id)
    return {"status": "ended_payout", "finishers": len(finishers), "payout_base": per, "payout_remainder": rem, **snap}


async def get_platform_revenue_stats(session: AsyncSession, days: int = 30) -> dict:
    """Get platform revenue statistics from forfeited stakes."""
    from datetime import datetime, timezone as dt_tz, timedelta
    
    from uuid import UUID
    cutoff = datetime.now(dt_tz.utc) - timedelta(days=days)
    platform_id = UUID("00000000-0000-0000-0000-000000000000")
    
    # Total revenue from forfeited stakes
    total_revenue = await session.scalar(
        select(func.coalesce(func.sum(Ledger.amount), 0))
        .where(
            Ledger.participant_id == platform_id,
            Ledger.type == "PLATFORM_REVENUE",
            Ledger.created_at >= cutoff
        )
    ) or 0
    
    # Number of failed challenges that generated revenue
    failed_challenges = await session.scalar(
        select(func.count(func.distinct(Ledger.challenge_id)))
        .where(
            Ledger.participant_id == platform_id,
            Ledger.type == "PLATFORM_REVENUE", 
            Ledger.created_at >= cutoff
        )
    ) or 0
    
    return {
        "period_days": days,
        "total_revenue_tokens": int(total_revenue),
        "failed_challenges": int(failed_challenges),
        "avg_revenue_per_failed_challenge": int(total_revenue / max(1, failed_challenges)) if failed_challenges > 0 else 0
    }