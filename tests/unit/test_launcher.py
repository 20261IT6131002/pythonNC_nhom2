"""The documented module launcher rejects unsafe config without leaking its URI."""

import os
import subprocess
import sys


def test_module_launcher_reports_safe_config_error():
    env = dict(os.environ, NOTEAPP_MONGO_URI="mongodb://user:private-password@example.com")
    result = subprocess.run(
        [sys.executable, "-m", "noteapp.main"], env=env, capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 1
    assert "Configure a local Mongo URI" in result.stderr
    assert "private-password" not in result.stderr
    assert "example.com" not in result.stderr
