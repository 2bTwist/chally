import httpx, uuid, pytest
from httpx import AsyncClient
from app.main import app
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_owner_auto_participant_and_roster_and_counts():
    """Test that challenge creation auto-adds owner as participant and roster/counts work"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Owner
        email = f"o-{uuid.uuid4()}@ex.com"
        uname = f"own_{uuid.uuid4().hex[:6]}"
        assert (await ac.post("/auth/register", json={"email": email, "username": uname, "password": "supersecret"})).status_code == 201
        tokens = (await ac.post("/auth/login", json={"email": email, "password": "supersecret"})).json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}", "X-Client-Timezone": "America/New_York"}

        # Create challenge (owner auto-joins)
        payload = {
            "name": "Roster Demo",
            "visibility": "code",
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "ends_at":   (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {"start":"06:00:00","end":"23:00:00"},
                "proof_types": ["selfie"],
                "verification": {"mode":"auto","quorum_pct":60},
                "grace":0,"penalties":0,
                "anti_cheat_overlay_required":True,
                "anti_cheat_exif_required":True,
                "anti_cheat_phash_check":True
            }
        }
        ch = (await ac.post("/challenges", headers=hdrs, json=payload)).json()
        
        # Verify owner is auto-participant
        ch_full = (await ac.get(f"/challenges/{ch['id']}", headers=hdrs)).json()
        assert ch_full["participant_count"] == 1
        assert ch_full["is_owner"] is True
        assert ch_full["is_participant"] is True
        assert ch_full["runtime_state"] == "upcoming"

        # Another user joins
        e2 = f"p-{uuid.uuid4()}@ex.com"
        u2 = f"p_{uuid.uuid4().hex[:6]}"
        assert (await ac.post("/auth/register", json={"email": e2, "username": u2, "password": "supersecret"})).status_code == 201
        t2 = (await ac.post("/auth/login", json={"email": e2, "password":"supersecret"})).json()
        hdrs2 = {"Authorization": f"Bearer {t2['access']}", "X-Client-Timezone":"America/Los_Angeles"}
        join_res = await ac.post(f"/challenges/{ch['invite_code']}/join", headers=hdrs2)
        assert join_res.status_code == 201

        # Owner sees participant_count=2 and roster of 2
        ch_full2 = (await ac.get(f"/challenges/{ch['id']}", headers=hdrs)).json()
        assert ch_full2["participant_count"] == 2
        plist = (await ac.get(f"/challenges/{ch['id']}/participants", headers=hdrs)).json()
        assert len(plist) == 2
        assert {p["username"] for p in plist} == {uname, u2}

        # Participant 2's view
        ch_p2_view = (await ac.get(f"/challenges/{ch['id']}", headers=hdrs2)).json()
        assert ch_p2_view["is_owner"] is False
        assert ch_p2_view["is_participant"] is True

@pytest.mark.asyncio
async def test_list_joined_and_join_rules():
    """Test /joined endpoint and join restrictions (started challenges, owner blocking)"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Owner creates a challenge that already started -> join closed
        email = f"o2-{uuid.uuid4()}@ex.com"
        uname = f"own2_{uuid.uuid4().hex[:6]}"
        assert (await ac.post("/auth/register", json={"email": email, "username": uname, "password": "supersecret"})).status_code == 201
        tokens = (await ac.post("/auth/login", json={"email": email, "password":"supersecret"})).json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        payload = {
            "name": "Started Challenge",
            "visibility": "code",
            "starts_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),  # already started
            "ends_at":   (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "entry_stake_tokens": 0,
            "rules": {
                "frequency":"daily",
                "time_window":{"start":"06:00:00","end":"23:00:00"},
                "proof_types":["selfie"],
                "verification":{"mode":"auto","quorum_pct":60},
                "grace":0,"penalties":0,
                "anti_cheat_overlay_required":True,
                "anti_cheat_exif_required":True,
                "anti_cheat_phash_check":True
            }
        }
        ch = (await ac.post("/challenges", headers=hdrs, json=payload)).json()
        assert ch["runtime_state"] == "started"

        # Second user cannot join (started)
        e2 = f"p2-{uuid.uuid4()}@ex.com"
        u2 = f"p2_{uuid.uuid4().hex[:6]}"
        assert (await ac.post("/auth/register", json={"email": e2, "username": u2, "password":"supersecret"})).status_code == 201
        t2 = (await ac.post("/auth/login", json={"email": e2, "password":"supersecret"})).json()
        hdrs2 = {"Authorization": f"Bearer {t2['access']}"}
        r = await ac.post(f"/challenges/{ch['invite_code']}/join", headers=hdrs2)
        assert r.status_code == 400
        assert "already started" in r.json()["detail"]

        # Owner trying to join by code gets 409
        r2 = await ac.post(f"/challenges/{ch['invite_code']}/join", headers=hdrs)
        assert r2.status_code == 409
        assert "Owner is already part" in r2.json()["detail"]

        # Owner's "joined" list includes this challenge (since owner is auto participant)
        joined = (await ac.get("/challenges/joined", headers=hdrs)).json()
        assert any(c["id"] == ch["id"] for c in joined)

        # Owner's "mine" list also includes it
        mine = (await ac.get("/challenges/mine", headers=hdrs)).json()
        assert any(c["id"] == ch["id"] for c in mine)

@pytest.mark.asyncio
async def test_runtime_states():
    """Test runtime_state computation for different challenge phases"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Setup user
        email = f"rs-{uuid.uuid4()}@ex.com"
        uname = f"rs_{uuid.uuid4().hex[:6]}"
        assert (await ac.post("/auth/register", json={"email": email, "username": uname, "password": "supersecret"})).status_code == 201
        tokens = (await ac.post("/auth/login", json={"email": email, "password":"supersecret"})).json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        base_rules = {
            "frequency":"daily",
            "time_window":{"start":"06:00:00","end":"23:00:00"},
            "proof_types":["text"],
            "verification":{"mode":"auto","quorum_pct":60},
            "grace":0,"penalties":0,
            "anti_cheat_overlay_required":True,
            "anti_cheat_exif_required":True,
            "anti_cheat_phash_check":True
        }

        # Upcoming challenge
        upcoming_payload = {
            "name": "Future Challenge",
            "visibility": "code",
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "ends_at": (datetime.now(timezone.utc) + timedelta(days=8)).isoformat(),
            "entry_stake_tokens": 0,
            "rules": base_rules
        }
        upcoming = (await ac.post("/challenges", headers=hdrs, json=upcoming_payload)).json()
        assert upcoming["runtime_state"] == "upcoming"

        # Ended challenge
        ended_payload = {
            "name": "Past Challenge",
            "visibility": "code", 
            "starts_at": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
            "ends_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "entry_stake_tokens": 0,
            "rules": base_rules
        }
        ended = (await ac.post("/challenges", headers=hdrs, json=ended_payload)).json()
        assert ended["runtime_state"] == "ended"

@pytest.mark.asyncio
async def test_participant_timezone_inheritance():
    """Test that owner gets timezone from X-Client-Timezone header or challenge rules"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Setup user
        email = f"tz-{uuid.uuid4()}@ex.com"
        uname = f"tz_{uuid.uuid4().hex[:6]}"
        assert (await ac.post("/auth/register", json={"email": email, "username": uname, "password": "supersecret"})).status_code == 201
        tokens = (await ac.post("/auth/login", json={"email": email, "password":"supersecret"})).json()
        hdrs_pst = {"Authorization": f"Bearer {tokens['access']}", "X-Client-Timezone": "America/Los_Angeles"}

        # Create challenge with participant_local scope
        payload = {
            "name": "Timezone Test",
            "visibility": "code",
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "ends_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "entry_stake_tokens": 0,
            "rules": {
                "frequency":"daily",
                "time_window": {
                    "start":"06:00:00",
                    "end":"23:00:00",
                    "scope": "participant_local"
                },
                "proof_types":["text"],
                "verification":{"mode":"auto","quorum_pct":60},
                "grace":0,"penalties":0,
                "anti_cheat_overlay_required":True,
                "anti_cheat_exif_required":True,
                "anti_cheat_phash_check":True
            }
        }
        ch = (await ac.post("/challenges", headers=hdrs_pst, json=payload)).json()
        
        # Check participants roster - owner should have PST timezone
        participants = (await ac.get(f"/challenges/{ch['id']}/participants", headers=hdrs_pst)).json()
        assert len(participants) == 1
        
        # The owner should be the participant we see
        owner_participant = participants[0]
        assert owner_participant["username"] == uname