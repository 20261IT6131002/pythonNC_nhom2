"""P1-AC13: safe config and loopback-only technical assumptions."""

import pytest

from noteapp.domain.errors import ValidationError
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import SystemClock


@pytest.mark.parametrize(
    ("uri", "database"),
    [
        ("mongodb://example.com", "noteapp_dev"),
        ("mongodb://127.0.0.1", "production"),
        ("mongodb+srv://example.com", "noteapp_dev"),
        ("not-a-uri", "noteapp_dev"),
        ("mongodb://127.0.0.1:bad", "noteapp_dev"),
    ],
)
def test_unsafe_configuration_rejected(uri, database):
    with pytest.raises(ValidationError):
        Config(uri, database)


def test_secrets_not_in_config_repr():
    config = Config("mongodb://user:secret@127.0.0.1", "noteapp_dev")
    assert "secret" not in repr(config)
    assert "user" not in repr(config)


def test_environment_required():
    with pytest.raises(ValidationError):
        Config.from_env({})


@pytest.mark.parametrize("timeout", ["bad", "0", "30001"])
def test_timeout_validation(timeout):
    with pytest.raises(ValidationError):
        Config.from_env(
            {"NOTEAPP_MONGO_URI": "mongodb://127.0.0.1", "NOTEAPP_MONGO_TIMEOUT_MS": timeout}
        )


def test_system_clock_is_aware_utc():
    assert SystemClock().now().utcoffset().total_seconds() == 0
