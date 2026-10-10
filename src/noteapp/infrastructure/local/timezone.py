"""OS/IANA resolution belongs outside core; never infer a fixed offset."""

import os
import warnings
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tzlocal import get_localzone_name


def resolve_timezone() -> ZoneInfo | None:
    try:
        key = os.environ.get("NOTEAPP_TIMEZONE")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            zone = ZoneInfo(key or get_localzone_name())
        return zone if isinstance(zone, ZoneInfo) else None
    except (ZoneInfoNotFoundError, ValueError, OSError, RuntimeError, Warning):
        return None
