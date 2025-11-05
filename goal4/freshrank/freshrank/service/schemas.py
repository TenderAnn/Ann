"""Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class DocumentPayload(BaseModel):
    doc_id: str
    chunk_id: Optional[str] = None
    relevance: float = Field(0.0, ge=0)
    effective_date: Optional[datetime] = None
    expired: bool = False
    publish_date: Optional[datetime] = None
    status: Optional[str] = None
    doc_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class RankRequest(BaseModel):
    query: Optional[str] = None
    intent: Optional[str] = None
    regulatory: Literal["auto", "on", "off"] = "auto"
    documents: List[DocumentPayload]


class RankedItem(BaseModel):
    doc_id: str
    chunk_id: Optional[str] = None
    final_score: float
    score_breakdown: dict
    tags: List[str] = []
    evidence: List[str] = []


class RankResponse(BaseModel):
    results: List[RankedItem]
