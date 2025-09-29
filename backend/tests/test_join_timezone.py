from __future__ import annotations
import httpx
import uuid
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_join_saves_client_timezone_header():
    """Test that joining a challenge saves timezone from X-Client-Timezone header"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login a user
        email = f"{uuid.uuid4()}@example.com"
        username = f"user_{uuid.uuid4().hex[:8]}"
        
        reg_response = await ac.post("/auth/register", json={
            "email": email, 
            "username": username, 
            "password": "supersecret",
            "full_name": "Test User"
        })
        assert reg_response.status_code == 201
        
        login_response = await ac.post("/auth/login", json={
            "email": email, 
            "password": "supersecret"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        # Create challenge with participant_local scope (default)
        challenge_payload = {
            "name": "Local Window Test",
            "description": "Test participant-local time windows", 
            "visibility": "code",
            "starts_at": "2025-01-10T00:00:00Z",
            "ends_at":   "2025-01-20T00:00:00Z",
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {
                    "start": "06:00:00",
                    "end": "23:00:00",
                    "scope": "participant_local"  # Participant's local time
                },
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 0, 
                "penalties": 0,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        
        challenge_response = await ac.post("/challenges", headers=hdrs, json=challenge_payload)
        assert challenge_response.status_code == 201
        challenge = challenge_response.json()
        
        # Join with PST timezone via header
        join_response = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers={**hdrs, "X-Client-Timezone": "America/Los_Angeles"}
        )
        assert join_response.status_code == 201
        participant = join_response.json()
        
        # Verify timezone was saved
        assert participant["timezone"] == "America/Los_Angeles"
        assert "challenge_id" in participant
        assert "user_id" in participant
        assert "joined_at" in participant


@pytest.mark.asyncio
async def test_join_saves_client_timezone_body():
    """Test that joining a challenge saves timezone from request body"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login a user
        email = f"{uuid.uuid4()}@example.com"
        username = f"user_{uuid.uuid4().hex[:8]}"
        
        reg_response = await ac.post("/auth/register", json={
            "email": email, 
            "username": username, 
            "password": "supersecret",
            "full_name": "Test User"
        })
        assert reg_response.status_code == 201
        
        login_response = await ac.post("/auth/login", json={
            "email": email, 
            "password": "supersecret"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        # Create challenge
        challenge_payload = {
            "name": "Body Timezone Test",
            "description": "Test timezone from body", 
            "visibility": "code",
            "starts_at": "2025-01-10T00:00:00Z",
            "ends_at":   "2025-01-20T00:00:00Z",
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {
                    "start": "06:00:00",
                    "end": "23:00:00"
                },
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 0, 
                "penalties": 0,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        
        challenge_response = await ac.post("/challenges", headers=hdrs, json=challenge_payload)
        assert challenge_response.status_code == 201
        challenge = challenge_response.json()
        
        # Join with timezone in body
        join_response = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers=hdrs,
            json={"timezone": "Europe/London"}
        )
        assert join_response.status_code == 201
        participant = join_response.json()
        
        # Verify timezone was saved
        assert participant["timezone"] == "Europe/London"


@pytest.mark.asyncio 
async def test_join_header_overrides_body():
    """Test that X-Client-Timezone header takes precedence over body timezone"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login a user
        email = f"{uuid.uuid4()}@example.com"
        username = f"user_{uuid.uuid4().hex[:8]}"
        
        reg_response = await ac.post("/auth/register", json={
            "email": email, 
            "username": username, 
            "password": "supersecret",
            "full_name": "Test User"
        })
        assert reg_response.status_code == 201
        
        login_response = await ac.post("/auth/login", json={
            "email": email, 
            "password": "supersecret"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        # Create challenge
        challenge_payload = {
            "name": "Header vs Body Test",
            "description": "Test header precedence over body", 
            "visibility": "code",
            "starts_at": "2025-01-10T00:00:00Z",
            "ends_at":   "2025-01-20T00:00:00Z",
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {
                    "start": "06:00:00",
                    "end": "23:00:00"
                },
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 0, 
                "penalties": 0,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        
        challenge_response = await ac.post("/challenges", headers=hdrs, json=challenge_payload)
        assert challenge_response.status_code == 201
        challenge = challenge_response.json()
        
        # Join with timezone in both header and body
        join_response = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers={**hdrs, "X-Client-Timezone": "Asia/Tokyo"},
            json={"timezone": "Europe/London"}
        )
        assert join_response.status_code == 201
        participant = join_response.json()
        
        # Header should win
        assert participant["timezone"] == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_join_defaults_to_utc():
    """Test that joining without timezone defaults to UTC"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login a user
        email = f"{uuid.uuid4()}@example.com"
        username = f"user_{uuid.uuid4().hex[:8]}"
        
        reg_response = await ac.post("/auth/register", json={
            "email": email, 
            "username": username, 
            "password": "supersecret",
            "full_name": "Test User"
        })
        assert reg_response.status_code == 201
        
        login_response = await ac.post("/auth/login", json={
            "email": email, 
            "password": "supersecret"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        # Create challenge
        challenge_payload = {
            "name": "Default Timezone Test",
            "description": "Test default timezone fallback", 
            "visibility": "code",
            "starts_at": "2025-01-10T00:00:00Z",
            "ends_at":   "2025-01-20T00:00:00Z",
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {
                    "start": "06:00:00",
                    "end": "23:00:00"
                },
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 0, 
                "penalties": 0,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        
        challenge_response = await ac.post("/challenges", headers=hdrs, json=challenge_payload)
        assert challenge_response.status_code == 201
        challenge = challenge_response.json()
        
        # Join without any timezone
        join_response = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers=hdrs
        )
        assert join_response.status_code == 201
        participant = join_response.json()
        
        # Should default to UTC
        assert participant["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_join_challenge_tz_scope_uses_challenge_timezone():
    """Test that challenge_tz scope uses the challenge's timezone as default"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login a user
        email = f"{uuid.uuid4()}@example.com"
        username = f"user_{uuid.uuid4().hex[:8]}"
        
        reg_response = await ac.post("/auth/register", json={
            "email": email, 
            "username": username, 
            "password": "supersecret",
            "full_name": "Test User"
        })
        assert reg_response.status_code == 201
        
        login_response = await ac.post("/auth/login", json={
            "email": email, 
            "password": "supersecret"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        # Create challenge with challenge_tz scope
        challenge_payload = {
            "name": "Challenge TZ Test",
            "description": "Test challenge timezone scope", 
            "visibility": "code",
            "starts_at": "2025-01-10T00:00:00Z",
            "ends_at":   "2025-01-20T00:00:00Z",
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {
                    "start": "06:00:00",
                    "end": "23:00:00",
                    "timezone": "America/New_York",
                    "scope": "challenge_tz"  # Use challenge timezone
                },
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 0, 
                "penalties": 0,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        
        challenge_response = await ac.post("/challenges", headers=hdrs, json=challenge_payload)
        assert challenge_response.status_code == 201
        challenge = challenge_response.json()
        
        # Join without providing timezone
        join_response = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers=hdrs
        )
        assert join_response.status_code == 201
        participant = join_response.json()
        
        # Should use challenge's timezone
        assert participant["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_rejoin_updates_timezone():
    """Test that rejoining a challenge updates the timezone"""
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login a user
        email = f"{uuid.uuid4()}@example.com"
        username = f"user_{uuid.uuid4().hex[:8]}"
        
        reg_response = await ac.post("/auth/register", json={
            "email": email, 
            "username": username, 
            "password": "supersecret",
            "full_name": "Test User"
        })
        assert reg_response.status_code == 201
        
        login_response = await ac.post("/auth/login", json={
            "email": email, 
            "password": "supersecret"
        })
        assert login_response.status_code == 200
        tokens = login_response.json()
        hdrs = {"Authorization": f"Bearer {tokens['access']}"}

        # Create challenge
        challenge_payload = {
            "name": "Rejoin Timezone Test",
            "description": "Test timezone update on rejoin", 
            "visibility": "code",
            "starts_at": "2025-01-10T00:00:00Z",
            "ends_at":   "2025-01-20T00:00:00Z",
            "entry_stake_tokens": 0,
            "rules": {
                "frequency": "daily",
                "time_window": {
                    "start": "06:00:00",
                    "end": "23:00:00"
                },
                "proof_types": ["selfie"],
                "verification": {"mode": "auto", "quorum_pct": 60},
                "grace": 0, 
                "penalties": 0,
                "anti_cheat_overlay_required": True,
                "anti_cheat_exif_required": True,
                "anti_cheat_phash_check": True
            }
        }
        
        challenge_response = await ac.post("/challenges", headers=hdrs, json=challenge_payload)
        assert challenge_response.status_code == 201
        challenge = challenge_response.json()
        
        # First join with PST
        join_response1 = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers={**hdrs, "X-Client-Timezone": "America/Los_Angeles"}
        )
        assert join_response1.status_code == 201
        participant1 = join_response1.json()
        assert participant1["timezone"] == "America/Los_Angeles"
        
        # Rejoin with different timezone
        join_response2 = await ac.post(
            f"/challenges/{challenge['invite_code']}/join",
            headers={**hdrs, "X-Client-Timezone": "Europe/London"}
        )
        assert join_response2.status_code == 201
        participant2 = join_response2.json()
        
        # Should update timezone and keep same participant ID
        assert participant2["timezone"] == "Europe/London"
        assert participant2["id"] == participant1["id"]  # Same participant record