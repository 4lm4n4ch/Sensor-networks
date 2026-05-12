import pytest
import numpy as np
from wsnsim.sim import Scheduler, SimClock
from wsnsim.utils.logger import TraceLogger
from wsnsim.utils.rng import RNG
from wsnsim.metrics.energy import energy_per_bit

def test_sim_clock_behavior():
    clock = SimClock(start=10.0)
    assert clock.now == 10.0
    
    clock.advance_to(15.0)
    assert clock.now == 15.0
    
    with pytest.raises(ValueError, match="Simulation clock cannot go backwards"):
        clock.advance_to(5.0)
    
    clock.reset(start=0.0)
    assert clock.now == 0.0

def test_scheduler_deterministic_ordering():
    scheduler = Scheduler(seed=42)
    execution = []

    def callback(payload):
        execution.append(payload)

    # Same time, different priority
    scheduler.schedule(time=1.0, callback=callback, priority=10, payload="p10")
    scheduler.schedule(time=1.0, callback=callback, priority=5, payload="p5")
    
    # Same time, same priority (should follow sequence)
    scheduler.schedule(time=2.0, callback=callback, priority=0, payload="s1")
    scheduler.schedule(time=2.0, callback=callback, priority=0, payload="s2")
    
    # Chronological
    scheduler.schedule(time=0.5, callback=callback, payload="first")

    scheduler.run()
    assert execution == ["first", "p5", "p10", "s1", "s2"]

def test_scheduler_until_boundary():
    scheduler = Scheduler()
    execution = []
    
    def callback(payload):
        execution.append(payload)

    scheduler.schedule(time=1.0, callback=callback, payload=1)
    scheduler.schedule(time=2.0, callback=callback, payload=2)
    scheduler.schedule(time=3.0, callback=callback, payload=3)

    scheduler.run(until=2.5)
    assert execution == [1, 2]
    assert scheduler.clock.now == 2.0
    assert scheduler.queued_events == 1

def test_scheduler_past_scheduling_fails():
    scheduler = Scheduler()
    scheduler.clock.advance_to(10.0)
    
    with pytest.raises(ValueError, match="Cannot schedule events in the past"):
        scheduler.schedule(time=5.0, callback=lambda x: None)

def test_trace_logger():
    trace = TraceLogger(enabled=True)
    trace.log(sim_time=1.0, message="test_event", key="value")
    
    assert len(trace.records) == 1
    assert trace.records[0].sim_time == 1.0
    assert trace.records[0].message == "test_event"
    assert trace.records[0].details["key"] == "value"
    
    trace.disable()
    trace.log(sim_time=2.0, message="ignored")
    assert len(trace.records) == 1
    
    trace.clear()
    assert len(trace.records) == 0

def test_rng_reproducibility():
    rng1 = RNG(seed=123)
    rng2 = RNG(seed=123)
    
    results1 = [rng1.rand() for _ in range(10)]
    results2 = [rng2.rand() for _ in range(10)]
    
    assert results1 == results2

def test_metrics_energy():
    assert energy_per_bit(100, 10) == 10.0
    assert energy_per_bit(100, 0) == float('inf')
