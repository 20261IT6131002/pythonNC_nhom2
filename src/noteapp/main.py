"""Runnable launcher and explicit resource lifecycle."""

import sys

from noteapp.bootstrap import build_runtime
from noteapp.domain.errors import NoteAppError


def main() -> int:
    try:
        runtime = build_runtime()
    except NoteAppError:
        print("Cannot start NoteApp. Configure a local Mongo URI and isolated DB.", file=sys.stderr)
        return 1
    try:
        runtime.window.root.mainloop()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
