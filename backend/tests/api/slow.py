"""Functions the real process pool runs in tests (spawned workers import them by name)."""

import time


def sleep_for(seconds: float) -> str:
    time.sleep(seconds)
    return "done"
