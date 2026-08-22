def test_allows_the_configured_frontend_origin(client):
    response = client.get("/health/live", headers={"Origin": "http://localhost:5173"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_rejects_an_unapproved_origin(client):
    response = client.get("/health/live", headers={"Origin": "http://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers
