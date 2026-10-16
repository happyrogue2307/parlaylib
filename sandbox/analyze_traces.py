#!/usr/bin/env python3
"""Non-greediness analysis of scheduler traces.

The benchmark (delaunay_scheduler_testing.cpp) appends one row per run to
trace_results/runs.csv with two sums over the 400 ns sample columns, where
S is the number of workers in state 'S' in a column:

  steal_while_ready = sum of S * [ready tasks > 0]
  min_steal_ready   = sum of min(S, ready tasks)

The default mode groups the runs by (algo, p, n) and reports the mean and
standard deviation of these sums and of the relative metrics

  rel_steal_while_ready = steal_while_ready / columns
  rel_min_steal_ready   = min_steal_ready / columns

(non-greedy worker-frames per total frames, between 0 and p), each computed
per run before averaging. If a (algo, p, n, run) appears more than once, the
last row wins, so a rerun replaces the earlier result. Writes summary.csv and
non_greediness.txt next to runs.csv.

The --grid mode computes the same two sums directly from .grid.txt files
(one row per worker with one state character per sample: W/S/A/D/., followed
by a final row of space-separated ready-task counts), to cross-check the C++
numbers.

Usage: analyze_traces.py [runs.csv]          (default: trace_results/runs.csv)
       analyze_traces.py --grid grid files...
"""
import csv
import os
import statistics
import sys
from collections import defaultdict


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


def grid_mode(paths):
    if not paths:
        sys.exit("no grid files given")
    print(f"{'file':<48} {'workers':>7} {'columns':>9} {'S*[ready>0]':>12} {'min(S,ready)':>13}")
    for path in paths:
        workers, cols, swr, msr = analyze(path)
        print(f"{os.path.relpath(path):<48} {workers:>7} {cols:>9} {swr:>12} {msr:>13}")


def mean_std(values):
    return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def aggregate(runs_path):
    latest = {}
    with open(runs_path) as f:
        for row in csv.DictReader(f):
            latest[(row["algo"], int(row["p"]), int(row["n"]), int(row["run"]))] = row

    groups = defaultdict(list)
    for (algo, p, n, _), row in latest.items():
        groups[(algo, p, n)].append(row)

    summary = []
    for (algo, p, n), rows in sorted(groups.items()):
        def col(name, f=int):
            return [f(r[name]) for r in rows]
        columns = col("columns")
        swr, msr = col("steal_while_ready"), col("min_steal_ready")
        entry = {"algo": algo, "p": p, "n": n, "runs": len(rows)}
        for name, values in [("columns", columns),
                             ("elapsed_ms", [e / 1e6 for e in col("elapsed_ns")]),
                             ("steal_while_ready", swr),
                             ("min_steal_ready", msr),
                             ("rel_steal_while_ready", [s / c for s, c in zip(swr, columns)]),
                             ("rel_min_steal_ready", [m / c for m, c in zip(msr, columns)])]:
            entry[f"mean_{name}"], entry[f"std_{name}"] = mean_std(values)
        summary.append(entry)
    return summary


def main():
    if sys.argv[1:2] == ["--grid"]:
        grid_mode(sys.argv[2:])
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    runs_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(script_dir, "trace_results", "runs.csv")
    if not os.path.exists(runs_path):
        sys.exit(f"{runs_path} not found; run delaunay_test first")
    out_dir = os.path.dirname(os.path.abspath(runs_path))
    summary = aggregate(runs_path)

    summary_path = os.path.join(out_dir, "summary.csv")
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    table = [f"{'algo':<9} {'p':>3} {'n':>9} {'runs':>4} {'columns':>11} {'elapsed ms':>11} "
             f"{'S*[ready>0]/col':>18} {'min(S,ready)/col':>18}"]
    for e in summary:
        table.append(f"{e['algo']:<9} {e['p']:>3} {e['n']:>9} {e['runs']:>4} {e['mean_columns']:>11.0f} "
                     f"{e['mean_elapsed_ms']:>11.2f} "
                     f"{e['mean_rel_steal_while_ready']:>9.4f} ± {e['std_rel_steal_while_ready']:<6.4f} "
                     f"{e['mean_rel_min_steal_ready']:>9.4f} ± {e['std_rel_min_steal_ready']:<6.4f}")
    print("\n".join(table))

    table_path = os.path.join(out_dir, "non_greediness.txt")
    with open(table_path, "w") as f:
        f.write("\n".join(table) + "\n")
    print(f"\nwrote {os.path.relpath(summary_path)} and {os.path.relpath(table_path)}")


if __name__ == "__main__":
    main()
