import httpx
from httpx import AsyncClient
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app
import uuid

import pytest

@pytest.mark.asyncio
async def test_register_login_me():
    # Use unique email and username for each test run
    unique_email = f"test-{uuid.uuid4()}@example.com"
    unique_username = f"user_{uuid.uuid4().hex[:8]}"
    
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # register
        r = await ac.post("/auth/register", json={"email": unique_email, "username": unique_username, "password": "supersecret"})
        assert r.status_code == status.HTTP_201_CREATED
        # login
        r = await ac.post("/auth/login", json={"email": unique_email, "password": "supersecret"})
        assert r.status_code == 200
        tokens = r.json()
        assert "access" in tokens and "refresh" in tokens
        # me with access token
        me = await ac.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"})
        assert me.status_code == 200
        body = me.json()
        assert body["email"] == unique_email
        assert body["username"] == unique_username.lower()
        # refresh to new pair
        r = await ac.post("/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh']}"})
        assert r.status_code == 200
        tokens2 = r.json()
        assert tokens2["access"] != tokens["access"]
