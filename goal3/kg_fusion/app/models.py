from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    text: str = Field(..., description="原始口语问题")
    intent: Optional[str] = Field(None, description="可选：外部指定意图")
    slots: Optional[Dict[str, Any]] = Field(None, description="可选：外部指定槽位")


class PlanOut(BaseModel):
    ok: bool = True
    intent: Optional[str] = None
    slots: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None
    threshold: Optional[float] = None
    canonical_candidates: List[str] = Field(default_factory=list)
    need_clarify: bool = False
    plan: Dict[str, Any] = Field(default_factory=dict)
    results: List[Dict[str, Any]] = Field(default_factory=list)
    debug: Dict[str, Any] = Field(default_factory=dict)
