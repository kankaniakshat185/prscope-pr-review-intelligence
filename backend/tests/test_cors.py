def test_unlisted_origin_is_not_granted_cors_access(client):
    r = client.options(
        "/api/analysis/analyze",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") is None


def test_allowed_extension_origin_is_granted_cors_access(client):
    origin = "chrome-extension://jfngcklfbiljgpoeehlkpkackahgopoc"
    r = client.options(
        "/api/analysis/analyze",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == origin
