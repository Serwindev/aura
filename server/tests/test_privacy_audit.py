"""The privacy contract as a regression test: the static audit (scripts/privacy_audit.py) must pass,
and it must actually catch a violation when one is planted."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("privacy_audit", ROOT / "scripts" / "privacy_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_privacy_contract_holds():
    res = audit.scan()
    assert res["findings"] == []


def test_audit_catches_a_planted_violation(tmp_path, monkeypatch):
    web = tmp_path / "web"
    web.mkdir()
    (web / "bad.js").write_text("navigator.geolocation.getCurrentPosition(() => {}); fetch('https://tracker.example.org/x')")
    monkeypatch.setattr(audit, "WEB", web)
    found = " ".join(audit.scan()["findings"])
    assert "location" in found and "tracker.example.org" in found


def test_audit_catches_an_extra_android_permission(tmp_path, monkeypatch):
    m = tmp_path / "AndroidManifest.xml"
    m.write_text('<manifest><application android:allowBackup="false"></application>'
                 '<uses-permission android:name="android.permission.RECORD_AUDIO" />'
                 '<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" /></manifest>')
    monkeypatch.setattr(audit, "MANIFEST", m)
    found = " ".join(audit.scan()["findings"])
    assert "ACCESS_FINE_LOCATION" in found
