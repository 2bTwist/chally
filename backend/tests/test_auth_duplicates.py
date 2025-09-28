import httpx
from httpx import AsyncClient
from fastapi import status
from app.main import app
import uuid
import pytest


@pytest.mark.asyncio
async def test_duplicate_email():
    """Test that registering with a duplicate email returns 409"""
    unique_id = str(uuid.uuid4())[:8]
    email = f"duplicate-{unique_id}@example.com"
    
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # First registration should succeed
        r1 = await ac.post("/auth/register", json={
            "email": email,
            "username": f"user1_{unique_id}",
            "password": "password1"
        })
        assert r1.status_code == status.HTTP_201_CREATED
        
        # Second registration with same email should fail
        r2 = await ac.post("/auth/register", json={
            "email": email,
            "username": f"user2_{unique_id}",
            "password": "password2"
        })
        assert r2.status_code == 409
        assert "email" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_username():
    """Test that registering with a duplicate username returns 409"""
    unique_id = str(uuid.uuid4())[:6]  # Shorter to fit in 20 char limit
    username = f"dupuser_{unique_id}"  # Total: dupuser_ (8) + 6 = 14 chars
    
    async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # First registration should succeed
        r1 = await ac.post("/auth/register", json={
            "email": f"user1-{unique_id}@example.com",
            "username": username,
            "password": "password1"
        })
        assert r1.status_code == status.HTTP_201_CREATED
        
        # Second registration with same username should fail
        r2 = await ac.post("/auth/register", json={
            "email": f"user2-{unique_id}@example.com",
            "username": username,
            "password": "password2"
        })
        assert r2.status_code == 409
        assert "username" in r2.json()["detail"].lower()