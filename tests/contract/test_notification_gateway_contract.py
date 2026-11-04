"""P3B-06: PlyerGateway keeps the NotificationGateway contract and hides provider details."""

import pytest

from noteapp.application.ports.notification_gateway import NotificationGateway
from noteapp.domain.errors import NotificationFailure
from noteapp.infrastructure.notifications.plyer_gateway import PlyerGateway


class Recorder:
    def __init__(self, error=None):
        self.calls, self.error = [], error

    def notify(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append(kwargs)


def test_gateway_satisfies_the_port_and_passes_plain_text_only():
    recorder = Recorder()
    gateway = PlyerGateway(recorder)
    assert isinstance(gateway, NotificationGateway)
    gateway.notify("Nhắc nhở", "Họp nhóm")
    (call,) = recorder.calls
    assert call["title"] == "Nhắc nhở" and call["message"] == "Họp nhóm"
    assert call["app_name"] == "NoteApp"


@pytest.mark.parametrize(
    "error", [NotImplementedError("no backend"), OSError("/root/x"), Exception]
)
def test_any_provider_failure_becomes_a_sanitized_notification_failure(error):
    with pytest.raises(NotificationFailure) as raised:
        PlyerGateway(Recorder(error)).notify("t", "m")
    assert "/root" not in str(raised.value) and "backend" not in str(raised.value)
    assert raised.value.__cause__ is None


def test_missing_plyer_backend_is_a_notification_failure(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name == "plyer":
            raise ImportError("no plyer")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny)
    with pytest.raises(NotificationFailure):
        PlyerGateway().notify("t", "m")
