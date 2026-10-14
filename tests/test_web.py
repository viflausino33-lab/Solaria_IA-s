from fastapi.testclient import TestClient

from solaria_ia.main import app


def test_homepage_serves_solaria_web_interface():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Solaria IA" in response.text
    assert 'id="task-form"' in response.text
    assert 'fetch("/v1/tasks"' in response.text
