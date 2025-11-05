from __future__ import annotations

from fastapi.testclient import TestClient

from freshrank.service import api

client = TestClient(api.app)


def test_reload_endpoint_triggers_pipeline_reload(monkeypatch):
    calls = {"count": 0}

    def fake_reload():
        calls["count"] += 1

    monkeypatch.setattr(api.pipeline, "reload", fake_reload)
    response = client.post("/admin/reload-config")
    assert response.status_code == 200
    assert calls["count"] == 1


def test_regulatory_override_via_query(monkeypatch):
    captured = {}

    def fake_rank(documents, regulatory=True):  # noqa: D401
        captured["regulatory"] = regulatory
        return []

    monkeypatch.setattr(api.pipeline, "rank", fake_rank)
    body = {"documents": [], "query": None, "intent": None, "regulatory": "auto"}
    resp = client.post("/rerank?regulatory=off", json=body)
    assert resp.status_code == 200
    assert captured["regulatory"] is False
