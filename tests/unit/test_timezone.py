"""CF-04: invalid/missing IANA config fails closed without affecting other reads."""

from zoneinfo import ZoneInfo

from noteapp.infrastructure.local.timezone import resolve_timezone


def test_explicit_iana_override(monkeypatch):
    monkeypatch.setenv("NOTEAPP_TIMEZONE", "America/New_York")
    assert resolve_timezone().key == "America/New_York"


def test_invalid_zone_is_not_silently_utc(monkeypatch):
    monkeypatch.setenv("NOTEAPP_TIMEZONE", "invalid/zone")
    assert resolve_timezone() is None


def test_os_mapping_and_unavailable_mapping(monkeypatch):
    monkeypatch.delenv("NOTEAPP_TIMEZONE", raising=False)
    monkeypatch.setattr("noteapp.infrastructure.local.timezone.get_localzone_name", lambda: "UTC")
    assert isinstance(resolve_timezone(), ZoneInfo)

    def unavailable():
        raise RuntimeError("OS zone not configured")

    monkeypatch.setattr("noteapp.infrastructure.local.timezone.get_localzone_name", unavailable)
    assert resolve_timezone() is None
