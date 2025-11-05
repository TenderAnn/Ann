from typing import Any, Dict, Optional

import httpx

from ..config import INTENT_BASE_URL


async def parse(text: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{INTENT_BASE_URL}/intent/parse", json={"text": text})
        resp.raise_for_status()
        return resp.json()


async def rewrite(
    text: str, intent: Optional[str], slots: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"text": text}
    if intent:
        payload["intent"] = intent
    if slots:
        payload["slots"] = slots

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{INTENT_BASE_URL}/intent/rewrite", json=payload)
        resp.raise_for_status()
        return resp.json()
