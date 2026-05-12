"""Hello Simulation example for wsnsim v0 core engine."""

from wsnsim.sim import Scheduler
from wsnsim.utils.logger import TraceLogger


def main() -> None:
    """Run a simple hello world simulation."""
    trace = TraceLogger(enabled=True)
    scheduler = Scheduler(seed=42, trace=trace)

    def say_hello(payload: str) -> None:
        print(f"[{scheduler.clock.now:06.2f}] EXEC: {payload}")

    scheduler.schedule(time=0.5, callback=say_hello, payload="Hello")
    scheduler.schedule(time=1.0, callback=say_hello, payload="Simulation")

    print(f"Starting simulation at t={scheduler.clock.now}...")
    executed = scheduler.run()
    print(f"Simulation finished. Executed {executed} events.")

    print("\nTrace records:")
    for record in trace.records:
        details = ", ".join(f"{k}={v}" for k, v in record.details.items())
        print(f"{record.sim_time:06.2f} | {record.message:15} | {details}")


if __name__ == "__main__":
    main()
