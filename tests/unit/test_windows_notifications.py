"""FR-10: suppressed Windows toasts never masquerade as an accepted delivery."""

import ctypes
from contextlib import nullcontext
from ctypes import wintypes
from types import SimpleNamespace

import pytest

from noteapp.domain.errors import NotificationFailure
from noteapp.infrastructure.notifications import plyer_gateway, windows_state


@pytest.fixture
def windows(monkeypatch):
    config = SimpleNamespace(enabled=1, state=5, hresult=0, queries=0, missing=False)

    def read_preference(key, name):
        assert name == "ToastEnabled"
        if config.missing:
            raise FileNotFoundError
        return config.enabled, 4

    class Query:
        def __call__(self, output):
            config.queries += 1
            ctypes.cast(output, ctypes.POINTER(wintypes.DWORD)).contents.value = config.state
            return config.hresult

    registry = SimpleNamespace(
        HKEY_CURRENT_USER=1,
        OpenKey=lambda *args: nullcontext(object()),
        QueryValueEx=read_preference,
    )
    monkeypatch.setattr(windows_state, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setitem(__import__("sys").modules, "winreg", registry)
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(shell32=SimpleNamespace(SHQueryUserNotificationState=Query())),
        raising=False,
    )
    config.registry = registry
    return config


def test_enabled_windows_accepts_notifications(windows):
    windows_state.ensure_notifications_available()
    assert windows.queries == 1


def test_disabled_windows_preference_blocks_before_provider_query(windows):
    windows.enabled = 0
    with pytest.raises(NotificationFailure, match="disabled"):
        windows_state.ensure_notifications_available()
    assert windows.queries == 0


@pytest.mark.parametrize("state", [1, 2, 3, 4, 6, 7])
def test_windows_busy_locked_fullscreen_and_quiet_states_are_not_accepted(windows, state):
    windows.state = state
    with pytest.raises(NotificationFailure, match="suppressing"):
        windows_state.ensure_notifications_available()


def test_unconfigured_preference_uses_default_but_still_checks_shell(windows):
    windows.missing = True
    windows_state.ensure_notifications_available()
    assert windows.queries == 1


def test_failed_shell_state_query_is_not_accepted(windows):
    windows.hresult = -1
    with pytest.raises(NotificationFailure):
        windows_state.ensure_notifications_available()


def test_non_windows_does_not_read_windows_preferences(windows, monkeypatch):
    monkeypatch.setattr(windows_state, "sys", SimpleNamespace(platform="linux"))
    windows.enabled = 0
    windows_state.ensure_notifications_available()
    assert windows.queries == 0


def test_cached_native_provider_rechecks_changed_windows_state(monkeypatch):
    calls = []
    gateway = plyer_gateway.PlyerGateway()
    recorder = SimpleNamespace(notify=lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(gateway, "_resolve", lambda: recorder)
    monkeypatch.setattr(plyer_gateway, "ensure_notifications_available", lambda: None)
    gateway.notify("Nhắc nhở", "Nội dung tổng hợp")

    def blocked():
        raise NotificationFailure("Windows is suppressing notifications.")

    monkeypatch.setattr(plyer_gateway, "ensure_notifications_available", blocked)
    with pytest.raises(NotificationFailure):
        gateway.notify("Nhắc nhở", "Nội dung tổng hợp")
    assert len(calls) == 1


def test_registry_access_failure_is_sanitized_at_gateway(windows):
    def denied(*args):
        raise PermissionError("private-path-or-user-data")

    windows.registry.OpenKey = denied
    with pytest.raises(NotificationFailure) as raised:
        plyer_gateway.PlyerGateway().notify("t", "m")
    assert "private" not in str(raised.value) and raised.value.__cause__ is None
