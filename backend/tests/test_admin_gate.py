from fastapi.testclient import TestClient

from app.main import app


def test_ingest_without_token_is_401():
    client = TestClient(app)
    res = client.post(
        "/api/knowledge/ingest",
        json={"title": "t", "content": "hello world"},
    )
    assert res.status_code == 401


def test_sessions_without_token_is_401():
    client = TestClient(app)
    res = client.get("/api/sessions")
    assert res.status_code == 401


def test_delete_document_without_token_is_401():
    client = TestClient(app)
    res = client.delete("/api/knowledge/documents/demo-doc")
    assert res.status_code == 401
