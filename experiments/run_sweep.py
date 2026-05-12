"""Simple experiment runner to run parameter sweeps (placeholder)."""

import argparse
from pathlib import Path


def run(args):
    print(f"Running sweep with params: {args}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="runs")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    run(args)


if __name__ == "__main__":
    main()
