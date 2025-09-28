import httpx, uuid
from httpx import AsyncClient
from fastapi import status
from app.main import app
import pytest
from datetime import datetime, timedelta, timezone

def _now():
    return datetime.now(timezone.utc)

async def _register_login(ac: AsyncClient):
    email = f"user-{uuid.uuid4()}@ex.com"
    username = f"user_{uuid.uuid4().hex[:8]}"
    assert (await ac.post("/auth/register", json={"email": email, "username": username, "password": "supersecret"})).status_code == 201
    r = await ac.post("/auth/login", json={"email": email, "password": "supersecret"})
    assert r.status_code == 200
    return r.json()["access"]

@pytest.mark.asyncio
async def test_create_and_join_challenge():
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        access = await _register_login(ac)
        hdrs = {"Authorization": f"Bearer {access}"}
        payload = {
            "name": "Daily Gym Photos",
            "description": "Proof every day",
            "visibility": "code",
            "starts_at": (_now() + timedelta(hours=1)).isoformat(),
            "ends_at": (_now() + timedelta(days=7)).isoformat(),
            "entry_stake_tokens": 10,
            "rules": {
                "frequency": "daily",
                "time_window": {"start": "18:00:00", "end": "22:00:00", "timezone": "America/New_York"},
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 1,
                "penalties": 2,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        r = await ac.post("/challenges", headers=hdrs, json=payload)
        assert r.status_code == status.HTTP_201_CREATED, r.text
        ch = r.json()
        assert ch["invite_code"]
        # Join by code (same user is allowed; participant record created)
        r2 = await ac.post(f"/challenges/{ch['invite_code']}/join", headers=hdrs)
        assert r2.status_code == 201
        # Fetch by id
        r3 = await ac.get(f"/challenges/{ch['id']}", headers=hdrs)
        assert r3.status_code == 200
        # List mine
        r4 = await ac.get("/challenges?mine=1", headers=hdrs)
        assert r4.status_code == 200
        assert any(c["id"] == ch["id"] for c in r4.json())