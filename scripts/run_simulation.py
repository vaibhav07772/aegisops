"""Run a simulated infrastructure scenario and write telemetry to data/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.logging_config import configure_logging, get_logger
from sim.config import SCENARIOS
from sim.models import IncidentScenario
from sim.runner import SimulationRunner

configure_logging()
logger = get_logger("scripts.run_simulation")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AegisOps Infrastructure Simulator")
    p.add_argument(
        "--scenario", "-s",
        choices=[s.value for s in IncidentScenario],
        default=IncidentScenario.NORMAL.value,
        help="Which scenario to simulate",
    )
    p.add_argument("--duration", "-d", type=float, default=60.0,
                   help="Duration in seconds (default: 60)")
    p.add_argument("--interval", "-i", type=float, default=1.0,
                   help="Tick interval in seconds (default: 1)")
    p.add_argument("--seed", type=int, default=None, help="Random seed")
    p.add_argument("--speedup", type=float, default=1.0,
                   help="Multiply tick speed (1.0 = realtime, 10.0 = 10x faster)")
    p.add_argument("--list-scenarios", action="store_true", help="List scenarios and exit")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_scenarios:
        print("\nAvailable scenarios:")
        for name, defn in SCENARIOS.items():
            print(f"  {name:<20} {defn.label}")
            print(f"    {defn.description}")
        return

    scenario = IncidentScenario(args.scenario)
    runner = SimulationRunner(
        scenario=scenario,
        duration_seconds=args.duration,
        tick_interval_seconds=args.interval,
        seed=args.seed,
        speedup=args.speedup,
    )
    meta = runner.run()

    print()
    print("=" * 55)
    print(" Simulation complete")
    print("=" * 55)
    print(f"  Run ID      : {meta.run_id}")
    print(f"  Scenario    : {meta.scenario.value}")
    print(f"  Duration    : {meta.duration_seconds:.2f}s")
    print(f"  Metrics     : {meta.metrics_count}")
    print(f"  Logs        : {meta.logs_count}")
    print(f"  Spans       : {meta.spans_count}")
    print(f"  Output dir  : data/{{metrics,logs,traces}}/{meta.run_id}.jsonl")


if __name__ == "__main__":
    main()