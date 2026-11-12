"""Send exactly once once Windows permits a banner; never change suppression settings."""
import json
import time
from pathlib import Path
from noteapp.infrastructure.notifications import plyer_gateway
from noteapp.infrastructure.notifications.windows_state import ensure_notifications_available
from noteapp.domain.errors import NotificationFailure

out = Path(__file__).resolve().parent / 'notification-watch.json'
deadline = time.monotonic() + 240
while time.monotonic() < deadline:
    try:
        ensure_notifications_available()
    except NotificationFailure:
        out.write_text(json.dumps({'status': 'waiting for Windows notification permission'}), encoding='utf-8')
        time.sleep(1)
    else:
        plyer_gateway.DISPLAY_SECONDS = 30  # QA probe only; production remains 10 seconds.
        plyer_gateway.PlyerGateway().notify('NoteApp QA - 30 seconds',
            'Windows notifications test. Please confirm you can see this banner.')
        out.write_text(json.dumps({'status': 'provider called', 'timeout_requested': 30,
                                  'display_confirmed': False}), encoding='utf-8')
        print('SENT ONCE: NoteApp QA - 30 seconds', flush=True)
        break
else:
    out.write_text(json.dumps({'status': 'Blocked', 'reason': 'Windows continued suppressing notifications for 240 seconds; no notification sent.'}), encoding='utf-8')
    print('Windows is still suppressing notifications. No notification sent.', flush=True)
