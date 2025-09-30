from __future__ import annotations
import os, hmac, hashlib, base64

_OVERLAY_SECRET = os.getenv("OVERLAY_SECRET", "dev-overlay-secret-change-me").encode()

def overlay_code(challenge_id: str, participant_id: str, slot_key: str, length: int = 6) -> str:
    """
    Deterministic 6-char code per (challenge, participant, slot).
    """
    msg = f"{challenge_id}.{participant_id}.{slot_key}".encode()
    digest = hmac.new(_OVERLAY_SECRET, msg, hashlib.sha256).digest()
    # Base32, strip padding, uppercase alpha+digits — then slice
    code = base64.b32encode(digest).decode("ascii").rstrip("=").upper()
    return code[:length]