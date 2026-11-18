"""Functions the real process pool runs in tests (spawned workers import them by name)."""

import time


def sleep_for(seconds: float) -> str:
    time.sleep(seconds)
    return "done"


def fail() -> None:
    raise RecursionError("a bug in the math engine")


def die() -> None:
    import os

    os._exit(1)
