"""Local QA evidence wrapper; never reads an application database configuration."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PY = str(ROOT / '.venv/Scripts/python.exe')
ENV = dict(os.environ, PYTHONUTF8='1', NOTEAPP_TEST_MONGO_URI='mongodb://127.0.0.1:27028',
           NOTEAPP_TEST_DB_NAME='noteapp_test_qa_srs_v2', NOTEAPP_REQUIRE_MONGO='1')
COMMANDS = {
    'unit-contract': [PY, '-m', 'pytest', '-q', 'tests/unit', 'tests/contract',
                      '--cov=noteapp.domain', '--cov=noteapp.application',
                      '--cov-report=term-missing', '--cov-report=xml:' + str(OUT / 'coverage.xml')],
    'integration': [PY, '-m', 'pytest', '-q', 'tests/integration', '-m',
                    'not ui and not native_secret_store'],
    'ui': [PY, '-m', 'pytest', '-q', 'tests/ui'],
    'desktop': [PY, '-m', 'pytest', '-vv', 'tests/integration/test_desktop.py'],
    'native-keyring': [PY, '-m', 'pytest', '-q', 'tests/integration/test_native_secret_store.py'],
    'search-benchmark': [PY, '-m', 'scripts.benchmark_phase2', '--output', str(OUT / 'search-benchmark.json')],
    'pin-benchmark': [PY, '-m', 'scripts.benchmark_pinned', '--output', str(OUT / 'pin-benchmark.json')],
    'backup-restore': [PY, str(OUT / 'backup_restore_qa.py')],
    'startup-benchmark': [PY, str(OUT / 'startup_qa.py')],
    'qa-probes': [PY, '-m', 'pytest', '-q', str(OUT / 'test_qa_probes.py')],
    'native-notification': [PY, str(OUT / 'native_notification_qa.py')],
}

stage = sys.argv[1]
command = COMMANDS[stage]
if stage in ('ui', 'desktop'):
    ENV['NOTEAPP_REQUIRE_UI'] = '1'
if stage == 'native-keyring':
    ENV['NOTEAPP_TEST_NATIVE_SECRET_STORE'] = '1'
if '-m' in command and 'pytest' in command:
    command += ['--basetemp=' + str(OUT / ('tmp-' + stage)),
                '--junitxml=' + str(OUT / (stage + '.xml'))]
started = time.time()
result = subprocess.run(command, cwd=ROOT, env=ENV, capture_output=True,
                        encoding='utf-8', errors='replace', timeout=1200)
log = result.stdout + result.stderr
(OUT / (stage + '.txt')).write_text(log, encoding='utf-8')
metadata = {'stage': stage, 'command': command, 'exit_code': result.returncode,
            'started_unix': started, 'elapsed_seconds': round(time.time() - started, 3)}
(OUT / (stage + '-run.json')).write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata))
print(log[-18000:])
sys.exit(result.returncode)
