#!/usr/bin/env python3
"""Plot the averaged non-greediness metrics from analyze_traces.py.

Reads trace_results/summary.csv and writes to trace_results/plots/:

  nongreedy_vs_n.png    mean relative metric vs n, one line per P, with
                        standard-deviation error bars over the runs
  nongreedy_heatmap.png mean relative metric for every (P, n), one cell each

Each figure has one column per algorithm and one row per metric:
  S*[ready>0] / columns  and  min(S,ready) / columns
i.e. non-greedy worker-frames per total frames (between 0 and P).

Usage: plot_traces.py [summary.csv]   (default: trace_results/summary.csv)
"""
import csv
import math
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
# One-hue blue ramp. For up to 5 ordered lines (one per P) use these
# validated ordinal steps; with more lines, sample the full ramp.
ORDINAL_5 = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"]
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

METRICS = [("rel_steal_while_ready", "S*[ready>0] / frames"),
           ("rel_min_steal_ready", "min(S, ready) / frames")]


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            r["p"], r["n"] = int(r["p"]), int(r["n"])
            for k in r:
                if k.startswith(("mean_", "std_")):
                    r[k] = float(r[k])
            rows.append(r)
    return rows


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(TEXT_SECONDARY)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)


def ordinal_colors(count):
    if count <= len(ORDINAL_5):
        # Spread the chosen steps over the validated ramp, darkest last.
        idx = [round(i * (len(ORDINAL_5) - 1) / max(count - 1, 1)) for i in range(count)]
        return [ORDINAL_5[i] for i in idx]
    cmap = LinearSegmentedColormap.from_list("ramp", RAMP[2:])
    return [cmap(i / (count - 1)) for i in range(count)]


def plot_vs_n(rows, algos, out_path):
    procs = sorted({r["p"] for r in rows})
    colors = ordinal_colors(len(procs))
    fig, axes = plt.subplots(len(METRICS), len(algos), figsize=(5.2 * len(algos), 3.6 * len(METRICS)),
                             squeeze=False, facecolor=SURFACE)
    for col, algo in enumerate(algos):
        for row, (metric, label) in enumerate(METRICS):
            ax = axes[row][col]
            style_axes(ax)
            for i, p in enumerate(procs):
                pts = sorted((r for r in rows if r["algo"] == algo and r["p"] == p), key=lambda r: r["n"])
                if not pts:
                    continue
                ax.errorbar([r["n"] for r in pts], [r[f"mean_{metric}"] for r in pts],
                            yerr=[r[f"std_{metric}"] for r in pts],
                            color=colors[i], linewidth=1.5, marker=MARKERS[i % len(MARKERS)], markersize=5,
                            markeredgecolor=SURFACE, markeredgewidth=1, capsize=2.5, elinewidth=1,
                            label=f"P = {p}")
            ax.set_xscale("log")
            ax.set_ylim(bottom=0)
            ax.set_xlabel("n (input size)", color=TEXT_SECONDARY, fontsize=9)
            ax.set_ylabel(label, color=TEXT_SECONDARY, fontsize=9)
            ax.set_title(f"{algo}: {label}", color=TEXT_PRIMARY, fontsize=10, loc="left")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.suptitle("Non-greediness vs input size (mean ± std over runs)", color=TEXT_PRIMARY, fontsize=12, y=0.995)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.955), ncol=len(procs), frameon=False,
               labelcolor=TEXT_PRIMARY, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def plot_heatmap(rows, algos, out_path):
    procs = sorted({r["p"] for r in rows})
    sizes = sorted({r["n"] for r in rows})
    cmap = LinearSegmentedColormap.from_list("ramp", RAMP)
    fig, axes = plt.subplots(len(METRICS), len(algos),
                             figsize=(1.0 * len(sizes) * len(algos) + 1.5 * len(algos), 0.7 * len(procs) * len(METRICS) + 1.2 * len(METRICS)),
                             squeeze=False, facecolor=SURFACE)
    for col, algo in enumerate(algos):
        for row, (metric, label) in enumerate(METRICS):
            ax = axes[row][col]
            cell = {(r["p"], r["n"]): r[f"mean_{metric}"] for r in rows if r["algo"] == algo}
            grid = [[cell.get((p, n), math.nan) for n in sizes] for p in procs]
            vmax = max((v for line in grid for v in line if not math.isnan(v)), default=1) or 1
            im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=vmax, aspect="auto", origin="lower")
            for i, line in enumerate(grid):
                for j, v in enumerate(line):
                    if not math.isnan(v):
                        ax.text(j, i, f"{v:.3g}", ha="center", va="center", fontsize=8,
                                color=SURFACE if v > 0.55 * vmax else TEXT_PRIMARY)
            ax.set_xticks(range(len(sizes)), [f"1e{round(math.log10(n))}" if n > 0 and math.log10(n).is_integer() else str(n) for n in sizes])
            ax.set_yticks(range(len(procs)), [str(p) for p in procs])
            ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.set_xlabel("n (input size)", color=TEXT_SECONDARY, fontsize=9)
            ax.set_ylabel("P (processors)", color=TEXT_SECONDARY, fontsize=9)
            ax.set_title(f"{algo}: {label}", color=TEXT_PRIMARY, fontsize=10, loc="left")
            cbar = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
            cbar.outline.set_visible(False)
            cbar.ax.tick_params(colors=TEXT_SECONDARY, labelsize=7)
    fig.suptitle("Non-greediness by processors and input size (mean over runs)", color=TEXT_PRIMARY, fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    summary_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(script_dir, "trace_results", "summary.csv")
    if not os.path.exists(summary_path):
        sys.exit(f"{summary_path} not found; run analyze_traces.py first")
    rows = load(summary_path)
    algos = sorted({r["algo"] for r in rows})

    out_dir = os.path.join(os.path.dirname(os.path.abspath(summary_path)), "plots")
    os.makedirs(out_dir, exist_ok=True)
    for name, plot in [("nongreedy_vs_n.png", plot_vs_n), ("nongreedy_heatmap.png", plot_heatmap)]:
        path = os.path.join(out_dir, name)
        plot(rows, algos, path)
        print(f"wrote {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
