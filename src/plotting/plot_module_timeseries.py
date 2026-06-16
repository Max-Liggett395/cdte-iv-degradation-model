#!/usr/bin/env python3
"""
plot_module_timeseries.py  --  src/plotting/

Reproduce the per-module timeseries figure (Performance Factor + Fill Factor
over time) from the master workbook produced by build_master_workbook.py.

Run from repo root:
    python src/plotting/plot_module_timeseries.py
    python src/plotting/plot_module_timeseries.py <workbook.xlsx> <bay> <out.png>
"""
import os
import sys
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_bay(workbook, bay, out_path):
    m = pd.read_excel(workbook, sheet_name="Master")
    m["datetime_local"] = pd.to_datetime(m["datetime_local"], errors="coerce")
    sub = m[m["bay"] == bay].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bay {bay}")

    mods = sorted(sub["module"].unique())
    colors = dict(zip(mods, plt.cm.tab10.colors))

    fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for k in mods:
        d = sub[sub["module"] == k]
        ax[0].plot(d["datetime_local"], d["performance_factor_pct"],
                   "o-", ms=5, lw=1.2, color=colors[k], label=k, alpha=0.85)
        ax[1].plot(d["datetime_local"], d["ff_meas"],
                   "o-", ms=5, lw=1.2, color=colors[k], label=k, alpha=0.85)
    ax[0].axhline(100, color="k", lw=0.8, ls="--", alpha=0.5)
    ax[0].set_ylabel("Performance Factor (%)\nmeasured / model")
    ax[0].set_title(f"Bay {bay} — Performance Factor over time (measured vs native model)")
    ax[1].set_ylabel("Fill Factor")
    ax[1].set_title(f"Bay {bay} — Fill Factor over time")
    ax[1].set_xlabel("Date")
    for a in ax:
        a.grid(alpha=0.3)
        a.legend(fontsize=8, ncol=4, loc="best")
        a.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    workbook = sys.argv[1] if len(sys.argv) > 1 else "outputs/master_iv_workbook.xlsx"
    bay = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out_path = sys.argv[3] if len(sys.argv) > 3 else f"outputs/fig_timeseries_bay{bay}.png"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    print("Wrote", plot_bay(workbook, bay, out_path))