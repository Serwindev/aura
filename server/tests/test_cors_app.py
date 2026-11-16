"""The Android app (mobile/, Capacitor) loads its pages from http://localhost inside the APK and calls the API
cross-origin. Only that origin may read API responses."""

from __future__ import annotations


def test_android_app_origin_is_allowed(env):
    client, _, _ = env
    r = client.options("/v1/meta", headers={"Origin": "http://localhost", "Access-Control-Request-Method": "GET",
                                            "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost"
    assert "access-control-allow-credentials" not in r.headers  # token goes in a header, never cookies
    r = client.get("/v1/meta", headers={"Origin": "http://localhost"})
    assert r.headers["access-control-allow-origin"] == "http://localhost"


def test_other_origins_are_not_allowed(env):
    client, _, _ = env
    for origin in ("https://evil.example.org", "http://localhost:3000", "http://192.168.1.9"):
        r = client.get("/v1/meta", headers={"Origin": origin})
        assert "access-control-allow-origin" not in r.headers
