import pytest

from wsnsim.sim import Scheduler


def test_scheduler_runs_event():
    s = Scheduler()
    calls = []

    def f(x):
        calls.append(x)

    s.schedule(1.0, f, "ok")
    s.run()
    assert calls == ["ok"]
