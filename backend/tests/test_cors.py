def test_unlisted_origin_is_not_granted_cors_access(client):
    r = client.options(
        "/api/analysis/analyze",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") is None


def test_published_extension_origin_is_granted_cors_access(client):
    origin = "chrome-extension://jfngcklfbiljgpoeehlkpkackahgopoc"
    r = client.options(
        "/api/analysis/analyze",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == origin


def test_unpacked_dev_extension_origin_is_granted_cors_access(client):
    # Chrome mints a different ID for "Load unpacked" than the published
    # Web Store ID (derived from the unpacked folder's absolute path).
    origin = "chrome-extension://gimimplokapoleofedgmdnghpcdhkmhm"
    r = client.options(
        "/api/analysis/analyze",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == origin


def test_preflight_allows_the_x_github_token_header(client):
    # Regression coverage for a real bug caught while building team-shared
    # review access verification: the frontend started sending a custom
    # X-Github-Token header, but CORS's allow_headers list didn't include
    # it. That class of bug is invisible to a Python test client hitting
    # routes directly - only an actual browser enforces CORS preflight -
    # so this simulates the preflight explicitly.
    origin = "chrome-extension://jfngcklfbiljgpoeehlkpkackahgopoc"
    r = client.options(
        "/api/analysis/workspace/reviews",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Github-Token,Authorization",
        },
    )
    assert r.status_code == 200
    allowed = r.headers.get("access-control-allow-headers", "")
    assert "x-github-token" in allowed.lower()
    assert "authorization" in allowed.lower()
