from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID

class VoteCreate(BaseModel):
    submission_id: UUID
    approve: bool