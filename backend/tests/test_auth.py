import httpx
from httpx import AsyncClient
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app
import uuid

import pytest

@pytest.mark.asyncio
async def test_register_login_me():
    # Use unique email for each test run
    unique_email = f"test-{uuid.uuid4()}@example.com"
    
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # register
        r = await ac.post("/auth/register", json={"email": unique_email, "password": "supersecret"})
        assert r.status_code == status.HTTP_201_CREATED
        # login
        r = await ac.post("/auth/login", json={"email": unique_email, "password": "supersecret"})
        assert r.status_code == 200
        tokens = r.json()
        assert "access" in tokens and "refresh" in tokens
        # me with access token
        r = await ac.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access']}"})
        assert r.status_code == 200
        assert r.json()["email"] == unique_email
        # refresh to new pair
        r = await ac.post("/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh']}"})
        assert r.status_code == 200
        tokens2 = r.json()
        assert tokens2["access"] != tokens["access"]
