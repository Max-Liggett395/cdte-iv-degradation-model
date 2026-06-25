#!/usr/bin/env python3
"""
plot_module_timeseries.py  --  src/plotting/

Per-module figures from the master workbook built by build_master_workbook.py.

USAGE
    python src/plotting/plot_module_timeseries.py <workbook.xlsx> <bays> <out_dir>

  <bays> controls what is produced:
    a single bay number   -> per-bay figures for that bay
        1   timeseries (PF+FF), corrections (raw vs STC), degradation
            (OC vs SC grouping labels appear only for Bay 1)
        2   same three figures, generic per-module grouping (no OC/SC labels)
    a comma list (e.g. 2,5) -> cross-bay figures pooling those bays:
        fig_compare_bays_2_5.png   raw vs STC, every module colored
        fig_avgloss_bays_2_5.png   average first->last change per parameter
    the word  all          -> per-bay figures for every bay present, PLUS the
                              cross-bay pair for bays 2 & 5 (whichever exist)

All quantities are recomputed in Python from the *value* columns of the Master
sheet (measured electricals + model-effective irradiance + SmartTemp cell
temperature); the workbook's formula columns are not read.

CORRECTION MATH  (G_ref = 1000 W/m^2, T_ref = 25 C; FS Series 7 TR1 coeffs)
    isc_stc = isc_meas * (G_ref/irr_model) / (1 + TK_Isc *(T_cell - T_ref))
    voc_stc = voc_meas /                     (1 + TK_Voc *(T_cell - T_ref))
    pmax_stc= pmax_meas* (G_ref/irr_model) / (1 + TK_Pmax*(T_cell - T_ref))
    jsc     = isc / MODULE_AREA_M2            (aperture current density)
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Reference conditions and datasheet temperature coefficients (per-degree-C).
G_REF, T_REF = 1000.0, 25.0
TK_PMAX, TK_VOC, TK_ISC = -0.0032, -0.0028, 0.0004

# FS-7520A aperture area (m^2) for Jsc = Isc / area. For a series-connected
# module this is aperture current density, not cell Jsc; percent-change in Jsc
# equals percent-change in Isc regardless of area.
MODULE_AREA_M2 = 2.80
JSC_LAB = "Jsc (A/m^2)" if MODULE_AREA_M2 else "Isc (A)"


def load_and_correct(workbook):
    """Read value columns from the Master sheet and add corrected columns."""
    m = pd.read_excel(workbook, sheet_name="Master")
    m["datetime_local"] = pd.to_datetime(m["datetime_local"], errors="coerce")

    G, Tc = m["irr_model_wm2"], m["cell_temp_model_c"]
    m["isc_stc"] = m["isc_meas_a"] * (G_REF / G) / (1 + TK_ISC * (Tc - T_REF))
    m["voc_stc"] = m["voc_meas_v"] / (1 + TK_VOC * (Tc - T_REF))
    m["pmax_stc"] = m["pmax_meas_w"] * (G_REF / G) / (1 + TK_PMAX * (Tc - T_REF))
    m["ff_meas"] = m["pmax_meas_w"] / (m["voc_meas_v"] * m["isc_meas_a"])
    m["ff_stc"] = m["pmax_stc"] / (m["voc_stc"] * m["isc_stc"])
    area = MODULE_AREA_M2 if MODULE_AREA_M2 else 1.0
    m["jsc_meas"] = m["isc_meas_a"] / area
    m["jsc_stc"] = m["isc_stc"] / area
    return m


def _modules(sub):
    """Sorted module list + a stable color map (tab10, or tab20 if >10)."""
    mods = sorted(sub["module"].unique())
    cmap = plt.cm.tab10 if len(mods) <= 10 else plt.cm.tab20
    colors = {mod: cmap(i % cmap.N) for i, mod in enumerate(mods)}
    return mods, colors


def _date_axis(ax):
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))


def _group_desc(bay):
    # OC vs SC distinction only exists physically for Bay 1.
    return "grouped by module; OC vs SC" if bay == 1 else "grouped by module"


# ---------------------------------------------------------------- per-bay ----
def plot_pf_ff(df, bay, out_path):
    sub = df[df["bay"] == bay].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bay {bay}")
    mods, colors = _modules(sub)

    fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for k in mods:
        d = sub[sub["module"] == k]
        ax[0].plot(d["datetime_local"], d["performance_factor_pct"],
                   "o-", ms=5, lw=1.2, color=colors[k], label=k, alpha=0.85)
        ax[1].plot(d["datetime_local"], d["ff_meas"],
                   "o-", ms=5, lw=1.2, color=colors[k], label=k, alpha=0.85)
    ax[0].axhline(100, color="k", lw=0.8, ls="--", alpha=0.5)
    ax[0].set_ylabel("Performance Factor (%)\nmeasured / model")
    ax[0].set_title(f"Bay {bay} - Performance Factor over time (measured vs native model)")
    ax[1].set_ylabel("Fill Factor")
    ax[1].set_title(f"Bay {bay} - Fill Factor over time")
    ax[1].set_xlabel("Date")
    ncol = min(len(mods), 7)
    for a in ax:
        _date_axis(a)
        a.legend(fontsize=8, ncol=ncol, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def plot_corrections(df, bay, out_path):
    """Voc / Jsc / Pmax over time, measured (left) vs STC-corrected (right)."""
    sub = df[df["bay"] == bay].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bay {bay}")
    mods, colors = _modules(sub)
    rows = [("voc_meas_v", "voc_stc", "Voc (V)"),
            ("jsc_meas", "jsc_stc", JSC_LAB),
            ("pmax_meas_w", "pmax_stc", "Pmax (W)")]

    fig, axes = plt.subplots(len(rows), 2, figsize=(13, 11),
                             sharex=True, sharey="row")
    for r, (mcol, ccol, ylab) in enumerate(rows):
        for c, (col, sub_title) in enumerate(
                [(mcol, "measured (raw)"), (ccol, "corrected to STC")]):
            ax = axes[r, c]
            for k in mods:
                d = sub[sub["module"] == k]
                ax.plot(d["datetime_local"], d[col], "o-", ms=4, lw=1.1,
                        color=colors[k], label=k, alpha=0.85)
            _date_axis(ax)
            if c == 0:
                ax.set_ylabel(ylab)
            ax.set_title(f"{ylab.split('(')[0].strip()} - {sub_title}", fontsize=10)
    axes[0, 1].legend(fontsize=8, ncol=min(len(mods), 4), loc="best")
    for c in range(2):
        axes[-1, c].set_xlabel("Date")
    fig.suptitle(f"Bay {bay} - measured vs STC-corrected ({_group_desc(bay)})",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def plot_degradation(df, bay, out_path):
    """Pmp / Voc / Jsc: actual STC value (left) and % change from baseline (right)."""
    sub = df[df["bay"] == bay].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bay {bay}")
    mods, colors = _modules(sub)
    rows = [("pmax_stc", "Pmp (W)"), ("voc_stc", "Voc (V)"), ("jsc_stc", JSC_LAB)]

    fig, axes = plt.subplots(len(rows), 2, figsize=(13, 11), sharex=True)
    for r, (col, ylab) in enumerate(rows):
        axL, axR = axes[r, 0], axes[r, 1]
        for k in mods:
            d = sub[sub["module"] == k].sort_values("datetime_local")
            axL.plot(d["datetime_local"], d[col], "o-", ms=4, lw=1.1,
                     color=colors[k], label=k, alpha=0.85)
            base = d[col].iloc[0]
            axR.plot(d["datetime_local"], 100.0 * (d[col] - base) / base,
                     "o-", ms=4, lw=1.1, color=colors[k], label=k, alpha=0.85)
        axR.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
        axL.set_ylabel(ylab)
        axR.set_ylabel("change (%)")
        name = ylab.split("(")[0].strip()
        axL.set_title(f"{name} - actual (STC)", fontsize=10)
        axR.set_title(f"{name} - change from first measurement (%)", fontsize=10)
        _date_axis(axL); _date_axis(axR)
    axes[0, 0].legend(fontsize=8, ncol=min(len(mods), 4), loc="best")
    for c in range(2):
        axes[-1, c].set_xlabel("Date")
    fig.suptitle(f"Bay {bay} - degradation view: actual STC values and change from baseline",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------- cross-bay ----
# Cross-bay figures color by BAY (all modules in a bay share one color) so the
# bay-to-bay contrast is the visual signal. Same figure types as the per-bay
# views, written as separate files.
from matplotlib.lines import Line2D


def _bay_colors(bays):
    cmap = plt.cm.Set1
    return {b: cmap(i) for i, b in enumerate(bays)}


def _bay_handles(bays, bay_colors):
    return [Line2D([0], [0], color=bay_colors[b], marker="o", lw=1.6,
                   label=f"Bay {b}") for b in bays]


def _plot_by_bay(ax, sub, bays, bay_colors, col):
    for b in bays:
        sb = sub[sub["bay"] == b]
        for k in sb["module"].unique():
            d = sb[sb["module"] == k].sort_values("datetime_local")
            ax.plot(d["datetime_local"], d[col], "o-", ms=4, lw=1.0,
                    color=bay_colors[b], alpha=0.65)
    _date_axis(ax)


def plot_multibay_pf_ff(df, bays, out_path):
    """Performance Factor + Fill Factor over time, colored by bay."""
    sub = df[df["bay"].isin(bays)].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bays {bays}")
    bc = _bay_colors(bays)
    fig, ax = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    _plot_by_bay(ax[0], sub, bays, bc, "performance_factor_pct")
    ax[0].axhline(100, color="k", lw=0.8, ls="--", alpha=0.5)
    ax[0].set_ylabel("Performance Factor (%)\nmeasured / model")
    ax[0].set_title("Performance Factor over time")
    _plot_by_bay(ax[1], sub, bays, bc, "ff_meas")
    ax[1].set_ylabel("Fill Factor")
    ax[1].set_title("Fill Factor over time")
    ax[1].set_xlabel("Date")
    ax[0].legend(handles=_bay_handles(bays, bc), fontsize=9, loc="best")
    tag = " vs ".join(f"Bay {b}" for b in bays)
    fig.suptitle(f"{tag} - timeseries (colored by bay)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def plot_multibay_corrections(df, bays, out_path):
    """Raw vs STC for Voc / Jsc / Pmax, colored by bay."""
    sub = df[df["bay"].isin(bays)].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bays {bays}")
    bc = _bay_colors(bays)
    rows = [("voc_meas_v", "voc_stc", "Voc (V)"),
            ("jsc_meas", "jsc_stc", JSC_LAB),
            ("pmax_meas_w", "pmax_stc", "Pmax (W)")]
    fig, axes = plt.subplots(len(rows), 2, figsize=(13, 11),
                             sharex=True, sharey="row")
    for r, (mcol, ccol, ylab) in enumerate(rows):
        for c, (col, sub_title) in enumerate(
                [(mcol, "measured (raw)"), (ccol, "corrected to STC")]):
            ax = axes[r, c]
            _plot_by_bay(ax, sub, bays, bc, col)
            if c == 0:
                ax.set_ylabel(ylab)
            ax.set_title(f"{ylab.split('(')[0].strip()} - {sub_title}", fontsize=10)
    for c in range(2):
        axes[-1, c].set_xlabel("Date")
    axes[0, 1].legend(handles=_bay_handles(bays, bc), fontsize=9, loc="best")
    tag = " vs ".join(f"Bay {b}" for b in bays)
    fig.suptitle(f"{tag} - measured vs STC-corrected (colored by bay)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def plot_multibay_degradation(df, bays, out_path):
    """Pmp / Voc / Jsc actual (STC) and % change from baseline, colored by bay."""
    sub = df[df["bay"].isin(bays)].sort_values("datetime_local")
    if sub.empty:
        raise SystemExit(f"No measurements found for bays {bays}")
    bc = _bay_colors(bays)
    rows = [("pmax_stc", "Pmp (W)"), ("voc_stc", "Voc (V)"), ("jsc_stc", JSC_LAB)]
    fig, axes = plt.subplots(len(rows), 2, figsize=(13, 11), sharex=True)
    for r, (col, ylab) in enumerate(rows):
        axL, axR = axes[r, 0], axes[r, 1]
        for b in bays:
            sb = sub[sub["bay"] == b]
            for k in sb["module"].unique():
                d = sb[sb["module"] == k].sort_values("datetime_local")
                axL.plot(d["datetime_local"], d[col], "o-", ms=4, lw=1.0,
                         color=bc[b], alpha=0.65)
                base = d[col].iloc[0]
                axR.plot(d["datetime_local"], 100.0 * (d[col] - base) / base,
                         "o-", ms=4, lw=1.0, color=bc[b], alpha=0.65)
        axR.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
        _date_axis(axL); _date_axis(axR)
        axL.set_ylabel(ylab); axR.set_ylabel("change (%)")
        name = ylab.split("(")[0].strip()
        axL.set_title(f"{name} - actual (STC)", fontsize=10)
        axR.set_title(f"{name} - change from first measurement (%)", fontsize=10)
    axes[0, 0].legend(handles=_bay_handles(bays, bc), fontsize=9, loc="best")
    for c in range(2):
        axes[-1, c].set_xlabel("Date")
    tag = " vs ".join(f"Bay {b}" for b in bays)
    fig.suptitle(f"{tag} - degradation view (colored by bay)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def _net_change_pct(d, col):
    """First-to-last percent change of a module's STC series (needs >=2 pts)."""
    v = d.sort_values("datetime_local")[col].dropna()
    if len(v) < 2:
        return np.nan
    return 100.0 * (v.iloc[-1] - v.iloc[0]) / v.iloc[0]


def plot_average_loss(df, bays, out_path):
    """Bay-averaged first->last % change in Pmp / Voc / Jsc (negative = loss)."""
    params = [("pmax_stc", "Pmp"), ("voc_stc", "Voc"), ("jsc_stc", "Jsc")]
    bc = _bay_colors(bays)
    means, stds, counts = {}, {}, {}
    for b in bays:
        sb = df[df["bay"] == b]
        means[b], stds[b], counts[b] = [], [], []
        for col, _ in params:
            vals = [_net_change_pct(sb[sb["module"] == k], col)
                    for k in sb["module"].unique()]
            vals = [v for v in vals if np.isfinite(v)]
            means[b].append(np.mean(vals) if vals else np.nan)
            stds[b].append(np.std(vals) if vals else np.nan)
            counts[b].append(len(vals))

    x = np.arange(len(params))
    width = 0.8 / max(len(bays), 1)
    fig, ax = plt.subplots(figsize=(9, 6))
    for i, b in enumerate(bays):
        off = (i - (len(bays) - 1) / 2) * width
        bars = ax.bar(x + off, means[b], width, yerr=stds[b], capsize=4,
                      color=bc[b], label=f"Bay {b} (n={counts[b][0]} modules)")
        for rect, val in zip(bars, means[b]):
            if np.isfinite(val):
                ax.annotate(f"{val:+.1f}%", (rect.get_x() + rect.get_width() / 2, val),
                            ha="center", va="bottom" if val >= 0 else "top", fontsize=8)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([p[1] for p in params])
    ax.set_ylabel("mean change, first to last measurement (%)\n(negative = loss)")
    tag = " vs ".join(f"Bay {b}" for b in bays)
    ax.set_title(f"Average parameter change by bay  ({tag})\nerror bars = spread across modules")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------- main ----
def per_bay(df, bay, out_dir):
    f1 = plot_pf_ff(df, bay, os.path.join(out_dir, f"fig_timeseries_bay{bay}.png"))
    f2 = plot_corrections(df, bay, os.path.join(out_dir, f"fig_corrections_bay{bay}.png"))
    f3 = plot_degradation(df, bay, os.path.join(out_dir, f"fig_degradation_bay{bay}.png"))
    return [f1, f2, f3]


def cross_bay(df, bays, out_dir):
    tag = "_".join(str(b) for b in bays)
    return [
        plot_multibay_pf_ff(df, bays, os.path.join(out_dir, f"fig_compare_timeseries_bays_{tag}.png")),
        plot_multibay_corrections(df, bays, os.path.join(out_dir, f"fig_compare_corrections_bays_{tag}.png")),
        plot_multibay_degradation(df, bays, os.path.join(out_dir, f"fig_compare_degradation_bays_{tag}.png")),
        plot_average_loss(df, bays, os.path.join(out_dir, f"fig_avgloss_bays_{tag}.png")),
    ]


def main(workbook, bays_arg, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    df = load_and_correct(workbook)
    written = []

    if str(bays_arg).strip().lower() == "all":
        present = sorted(int(b) for b in df["bay"].dropna().unique())
        for b in present:
            written += per_bay(df, b, out_dir)
        pair = [b for b in (2, 5) if b in present]
        if len(pair) >= 2:
            written += cross_bay(df, pair, out_dir)
    elif "," in str(bays_arg):
        bays = [int(x) for x in str(bays_arg).split(",") if x.strip()]
        written += cross_bay(df, bays, out_dir)
    else:
        written += per_bay(df, int(bays_arg), out_dir)

    for f in written:
        print("Wrote", f)


if __name__ == "__main__":
    workbook = sys.argv[1] if len(sys.argv) > 1 else "outputs/master_iv_workbook.xlsx"
    bays_arg = sys.argv[2] if len(sys.argv) > 2 else "1"
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "outputs"
    main(workbook, bays_arg, out_dir)
