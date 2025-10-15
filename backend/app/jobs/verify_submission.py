from __future__ import annotations
import asyncio
from datetime import datetime, timezone as dt_tz, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.db import SessionLocal
from app.models.submission import Submission
from app.models.challenge import Challenge, Participant
from app.schemas.challenge import RulesDSL
from app.services.slots import compute_slot
from app.services.overlay import overlay_code

# Hamming distance for hex phash strings
def _hamming_hex(a: str, b: str) -> int:
    try:
        return bin(int(a, 16) ^ int(b, 16)).count("1")
    except Exception:
        return 64  # treat as very different if bad data

def _parse_exif_datetime(meta: dict) -> datetime | None:
    # piexif returns dict with "Exif" and tag 36867 (DateTimeOriginal) or 306 (0th DateTime)
    try:
        exif = meta.get("exif") or {}
        raw = None
        # try ExifIFD.DateTimeOriginal (36867)
        raw = exif.get("Exif", {}).get("36867") or raw
        # fallback to 0th.DateTime (306)
        raw = raw or exif.get("0th", {}).get("306")
        if isinstance(raw, bytes):
            raw = raw.decode(errors="ignore")
        if isinstance(raw, str) and len(raw) >= 19:
            # Format "YYYY:MM:DD HH:MM:SS"
            s = raw.replace("\x00", "").strip()
            yyyy, mm, dd = s[0:4], s[5:7], s[8:10]
            HH, MM, SS = s[11:13], s[14:16], s[17:19]
            return datetime(int(yyyy), int(mm), int(dd), int(HH), int(MM), int(SS))
    except Exception:
        pass
    return None

async def _run(submission_id: str):
    async with SessionLocal() as session:
        s = await session.get(Submission, submission_id)
        if not s:
            return
        ch = await session.get(Challenge, s.challenge_id)
        p = await session.get(Participant, s.participant_id)
        rules = RulesDSL.model_validate(ch.rules_json)

        # Compute governing timezone & current window for the slot
        now = datetime.now(dt_tz.utc)
        scope = rules.time_window.scope or "participant_local"
        ch_tz = rules.time_window.timezone
        slot_key = s.slot_key
        # NOTE: use stored window_start_utc/window_end_utc to avoid recomputing differently
        win_start, win_end = s.window_start_utc, s.window_end_utc
        tz_name = p.timezone if scope == "participant_local" else (ch_tz or "UTC")

        # Collect checks
        checks_ok = True
        flags: list[str] = []

        # 1) Check for watermarking errors first
        meta = s.meta_json or {}
        if meta.get("watermark_error"):
            checks_ok = False
            flags.append("watermark_error")
        
        # 2) Watermark verification (embedded) if required
        embedded_code = meta.get("verification_code")
        if rules.anti_cheat_overlay_required:
            expected = overlay_code(str(ch.id), str(p.id), slot_key)
            if not embedded_code or embedded_code != expected:
                checks_ok = False
                flags.append("watermark_mismatch")

        # 3) EXIF required && within window (with small grace)
        if rules.anti_cheat_exif_required and s.mime_type and s.mime_type.startswith("image/"):
            exif_dt = _parse_exif_datetime(s.meta_json or {})
            if exif_dt is None:
                checks_ok = False
                flags.append("exif_missing")
            else:
                # Treat EXIF as local time in governing tz (common cameras store local wall clock)
                aware_local = exif_dt.replace(tzinfo=ZoneInfo(tz_name))
                exif_utc = aware_local.astimezone(dt_tz.utc)
                # 5-minute grace on both ends to absorb clock skew
                if not (win_start - timedelta(minutes=5) <= exif_utc <= win_end + timedelta(minutes=5)):
                    checks_ok = False
                    flags.append("exif_out_of_window")

        # 4) Perceptual hash: prevent too-similar submissions from same user
        ph = None
        if rules.anti_cheat_phash_check and s.mime_type and s.mime_type.startswith("image/"):
            # Use original phash (before watermarking) for duplicate detection
            ph = (s.meta_json or {}).get("original_phash") or (s.meta_json or {}).get("phash")
        if ph:
            recent = (
                await session.execute(
                    select(Submission)
                    .where(Submission.participant_id == s.participant_id, Submission.id != s.id)
                    .order_by(Submission.submitted_at.desc())
                    .limit(8)
                )
            ).scalars().all()
            too_similar = False
            for prev in recent:
                # Use original phash for comparison (before watermarking)
                prev_ph = (prev.meta_json or {}).get("original_phash") or (prev.meta_json or {}).get("phash")
                if prev_ph:
                    if _hamming_hex(ph, prev_ph) <= 5:
                        too_similar = True
                        break
            if too_similar:
                checks_ok = False
                flags.append("phash_duplicate_like")

        # Update submission
        meta = dict(s.meta_json or {})
        if flags:
            meta["flags"] = flags

        # Mode handling
        if rules.verification.mode == "auto" and checks_ok:
            s.status = "accepted"
        else:
            # route to quorum or manual review
            s.status = "pending"
        s.meta_json = meta
        await session.commit()

def verify_submission(submission_id: str):
    # RQ entry point (sync); run the async coroutine
    asyncio.run(_run(submission_id))