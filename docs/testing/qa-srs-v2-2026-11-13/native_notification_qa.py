import json
import time
from pathlib import Path
from noteapp.infrastructure.notifications.plyer_gateway import PlyerGateway
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner

runner = TaskRunner(max_workers=1)
try:
    assert runner.submit('qa-native-notification', 'notify', lambda: PlyerGateway().notify(
        'NoteApp QA', 'Synthetic QA test: Windows notification. No personal note content.'))
    deadline = time.monotonic() + 20
    events = []
    while not events and time.monotonic() < deadline:
        events = runner.drain()
        time.sleep(.01)
    assert events, 'Notification worker timed out.'
    result = events[0].result
    # The API returning successfully never proves OS display or user visibility.
    report = {'provider': 'native Windows plyer', 'call_completed': True,
              'provider_call_ok': result.ok,
              'error_code': result.error.value if result.error else None,
              'display_confirmed': False, 'status': 'Not Run',
              'attempt': 2,
              'first_attempt_observation': 'Inconclusive: user clarified they were away from the computer.',
              'limitation': 'Provider return and actual OS display are separate; waiting for user observation. OS-blocked settings not changed or tested.'}
finally:
    runner.close(wait=True)
(Path(__file__).resolve().parent / 'native-notification.json').write_text(
    json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
