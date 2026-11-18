"""Run sympy work in worker processes under a wall-clock limit.

The parser's size guards are the first line of defence; this is the backstop. A thread
can't be stopped and sympy holds the GIL, so only a separate process gives a real limit:
pebble kills a worker that runs over its timeout and starts a fresh one.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
from collections.abc import Callable
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, TypeVar

from pebble import ProcessExpired, ProcessPool

T = TypeVar("T")
log = logging.getLogger("app.mathpool")


class MathTimeout(Exception):
    """The math took longer than the limit; the request abstains."""


class MathFailure(Exception):
    """The math engine failed unexpectedly (a bug, or a worker that died); the request
    abstains instead of answering 500."""


def _warm_up() -> None:
    import app.math.pipeline  # noqa: F401  (import sympy once per worker, not per request)


class MathPool:
    """`workers=0` runs inline with no time limit: only for tests that don't test the limit."""

    def __init__(self, workers: int, timeout_s: float) -> None:
        self.workers = workers
        self.timeout_s = timeout_s
        self._pool: ProcessPool | None = None

    def start(self) -> None:
        if self.workers > 0 and self._pool is None:
            self._pool = ProcessPool(
                max_workers=self.workers,
                initializer=_warm_up,
                context=multiprocessing.get_context("spawn"),
            )

    def stop(self) -> None:
        if self._pool is not None:
            self._pool.stop()  # type: ignore[no-untyped-call]
            self._pool.join()
            self._pool = None

    async def run(self, fn: Callable[..., T], *args: Any) -> T:
        try:
            if self._pool is None:
                return fn(*args)
            future = self._pool.schedule(fn, args=args, timeout=self.timeout_s)
            result: T = await asyncio.wrap_future(future)
        except FutureTimeout as err:
            raise MathTimeout from err
        except (ProcessExpired, Exception) as err:
            # Logged by type only: the input may be a teacher's free text.
            log.error('{"event": "math_failure", "error": "%s"}', type(err).__name__)
            raise MathFailure from err
        return result
