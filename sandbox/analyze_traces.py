#!/usr/bin/env python3
"""Non-greediness analysis of parlay_trace_*.grid.txt files.

Each grid file has one row per worker (one state character per sample:
W/S/A/D/.) followed by a final row of space-separated ready-task counts,
one per sample. For every sample column we compute

  steal_while_ready = (#workers in 'S') * [ready tasks > 0]
  min_steal_ready   = min(#workers in 'S', ready tasks)

and sum both over all columns. The results table is printed and also
written to sandbox/trace_results/non_greediness.txt.

Usage: analyze_traces.py [grid files...]   (default: build/*.grid.txt)
"""
import glob
import os
import sys


def analyze(path):
    with open(path) as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]
    worker_rows, ready = lines[:-1], [int(x) for x in lines[-1].split()]

    num_cols = len(ready)
    for w, row in enumerate(worker_rows):
        if len(row) != num_cols:
            raise ValueError(f"{path}: worker row {w} has {len(row)} columns, "
                             f"ready row has {num_cols}")

    steal_while_ready = 0
    min_steal_ready = 0
    for col in range(num_cols):
        stealing = sum(1 for row in worker_rows if row[col] == 'S')
        steal_while_ready += stealing * (ready[col] > 0)
        min_steal_ready += min(stealing, ready[col])

    return len(worker_rows), num_cols, steal_while_ready, min_steal_ready


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(script_dir, "..", "build", "*.grid.txt")))
    if not paths:
        sys.exit("no grid files found")

    table = [f"{'file':<36} {'workers':>7} {'columns':>9} {'S*[ready>0]':>12} {'min(S,ready)':>13}"]
    for path in paths:
        workers, cols, swr, msr = analyze(path)
        table.append(f"{os.path.basename(path):<36} {workers:>7} {cols:>9} {swr:>12} {msr:>13}")
    print("\n".join(table))

    out_dir = os.path.join(script_dir, "trace_results")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "non_greediness.txt")
    with open(out_path, "w") as f:
        f.write("\n".join(table) + "\n")
    print(f"\nwrote {os.path.relpath(out_path)}")


if __name__ == "__main__":
    main()
