import os
import sys

# Ensure backend/ is on sys.path so `app` package is importable when pytest runs
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Also add repo root so `ml` package is importable (repo_root/ contains `ml`)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "EVision" in resp.json().get("message", "")


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
