"""P1-AC13: safe config and loopback-only technical assumptions."""

from pathlib import Path

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


@pytest.mark.parametrize(
    ("port", "valid"),
    [
        (1, True),
        (65535, True),
        (0, False),
        (65536, False),
    ],
)
def test_mongo_port_boundaries(port, valid):
    uri = f"mongodb://127.0.0.1:{port}"
    if valid:
        assert Config(uri, "noteapp_dev").mongo_uri == uri
    else:
        with pytest.raises(ValidationError):
            Config(uri, "noteapp_dev")


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


def test_localhost_loopback_allowed():
    config = Config("mongodb://localhost:27017", "noteapp_dev")
    assert config.db_name == "noteapp_dev"


def test_ipv6_loopback_allowed():
    config = Config("mongodb://[::1]:27017", "noteapp_dev")
    assert config.db_name == "noteapp_dev"


@pytest.mark.parametrize("timeout", [100, 30000])
def test_timeout_boundaries_allowed(timeout):
    config = Config("mongodb://127.0.0.1:27017", "noteapp_dev", timeout)
    assert config.timeout_ms == timeout


@pytest.mark.parametrize(
    "database",
    [
        "noteapp_dev_team2",
        "noteapp_dev_feature123",
        "noteapp_test_team2",
    ],
)
def test_isolated_database_names_allowed(database):
    config = Config("mongodb://127.0.0.1:27017", database)
    assert config.db_name == database


@pytest.mark.parametrize(
    ("seconds", "valid"),
    [(5, True), (30, True), (3600, True), (4, False), (3601, False), (0, False), (True, False)],
)
def test_reminder_poll_interval_boundaries(seconds, valid):
    if valid:
        assert (
            Config("mongodb://127.0.0.1", "noteapp_dev", 3000, seconds).reminder_poll_seconds
            == seconds
        )
    else:
        with pytest.raises(ValidationError):
            Config("mongodb://127.0.0.1", "noteapp_dev", 3000, seconds)


def test_reminder_poll_interval_comes_from_the_environment_with_a_default():
    base = {"NOTEAPP_MONGO_URI": "mongodb://127.0.0.1"}
    assert Config.from_env(base).reminder_poll_seconds == 30
    assert (
        Config.from_env({**base, "NOTEAPP_REMINDER_POLL_SECONDS": "10"}).reminder_poll_seconds == 10
    )
    with pytest.raises(ValidationError):
        Config.from_env({**base, "NOTEAPP_REMINDER_POLL_SECONDS": "often"})


def test_draft_directory_override_is_absolute_and_not_exposed_in_repr(tmp_path):
    directory = str(tmp_path / "private-profile")
    config = Config.from_env(
        {
            "NOTEAPP_MONGO_URI": "mongodb://127.0.0.1",
            "NOTEAPP_DRAFT_DIR": directory,
        }
    )
    assert config.draft_dir == directory
    assert "private-profile" not in repr(config)
    with pytest.raises(ValidationError):
        Config("mongodb://127.0.0.1", draft_dir="../relative")


def test_default_draft_profiles_and_key_names_are_isolated(monkeypatch, tmp_path):
    from noteapp.infrastructure.local.draft_paths import draft_directory, draft_key_name

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    first = draft_directory("noteapp_dev")
    second = draft_directory("noteapp_test_other")
    assert first != second and first.is_absolute() and second.is_absolute()
    assert "noteapp_dev" not in str(first)
    assert draft_key_name(first) != draft_key_name(second)
    assert draft_directory("ignored", str(tmp_path)) == Path(tmp_path)
