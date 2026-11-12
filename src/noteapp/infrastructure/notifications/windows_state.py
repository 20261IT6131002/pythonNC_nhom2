"""Read Windows notification suppression without changing user preferences."""

import sys

from noteapp.domain.errors import NotificationFailure


def ensure_notifications_available() -> None:
    if sys.platform != "win32":
        return

    import ctypes
    import winreg
    from ctypes import wintypes

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\PushNotifications",
        ) as key:
            enabled, _ = winreg.QueryValueEx(key, "ToastEnabled")
    except FileNotFoundError:
        # An absent preference leaves the Windows default enabled.
        enabled = 1
    if enabled == 0:
        raise NotificationFailure("Notifications are disabled in Windows settings.")

    state = wintypes.DWORD()
    query = ctypes.windll.shell32.SHQueryUserNotificationState
    query.argtypes = [ctypes.POINTER(wintypes.DWORD)]
    query.restype = ctypes.c_long
    # QUNS_ACCEPTS_NOTIFICATIONS=5. Other states can suppress the balloon even
    # though plyer's asynchronous notify() returns without an exception.
    if query(ctypes.byref(state)) != 0 or state.value != 5:
        raise NotificationFailure("Windows is currently suppressing notifications.")
