from fastapi.testclient import TestClient

from main import app


def test_baseline_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/baseline", params={"n": 3})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_custom_async_logger() -> None:
    with TestClient(app) as client:
        custom_response = client.get("/custom-async-await", params={"n": 1})

    assert custom_response.status_code == 200
