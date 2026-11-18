import asyncio
import time

import pytest

from app.math.pipeline import MathText, analyse_mistake
from app.mathpool import MathPool, MathTimeout
from tests.api.slow import sleep_for


@pytest.fixture(scope="module")
def pool() -> object:
    pool = MathPool(workers=1, timeout_s=1.0)
    pool.start()
    yield pool
    pool.stop()


def test_a_slow_task_is_killed_and_the_pool_recovers(pool: MathPool) -> None:
    start = time.monotonic()
    with pytest.raises(MathTimeout):
        asyncio.run(pool.run(sleep_for, 30))
    assert time.monotonic() - start < 5
    # The killed worker is replaced, and real math still runs.
    found = asyncio.run(
        pool.run(analyse_mistake, MathText("1/2 + 1/3"), None, MathText("2/5"), [], None)
    )
    assert found.rule_ids == ["add_tops_and_bottoms"]


def test_inline_mode_runs_in_process() -> None:
    assert asyncio.run(MathPool(0, 1.0).run(sleep_for, 0)) == "done"
