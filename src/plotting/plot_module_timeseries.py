#!/usr/bin/env python3
"""
plot_module_timeseries.py  --  src/plotting/

Per-module timeseries figures from the master workbook built by
build_master_workbook.py. Produces three figures:

  1) fig_timeseries_bay<N>.png    Performance Factor + Fill Factor over time
  2) fig_corrections_bay<N>.png   Voc / Isc(Jsc) / Pmax, measured vs STC
  3) fig_degradation_bay<N>.png   Pmp / Voc / Jsc, actual (STC) and percent
                                  change from each module's first measurement

All quantities are recomputed here in Python from the *value* columns of the
Master sheet (measured electricals + model-effective irradiance + SmartTemp
cell temperature). We deliberately do NOT read the workbook's corrected
columns: those are stored as Excel formulas and are only evaluated once Excel
opens the file, so reading them straight after `build` would yield blanks.

------------------------------------------------------------------------------
SOURCE DATA  (Master sheet columns, all stored as plain values)
    voc_meas_v, isc_meas_a, pmax_meas_w   measured Voc [V], Isc [A], Pmax [W]
    irr_model_wm2                         effective irradiance (AOI-derated) [W/m^2]
    cell_temp_model_c                     SmartTemp cell temperature [deg C]
    performance_factor_pct                100 x measured Pmax / model Pmax [%]
    datetime_local, bay, module, config   identity

CORRECTION MATH  (G_ref = 1000 W/m^2, T_ref = 25 C; FS Series 7 TR1 coeffs)
    isc_stc = isc_meas * (G_ref/irr_model) / (1 + TK_Isc *(T_cell - T_ref))
    voc_stc = voc_meas /                     (1 + TK_Voc *(T_cell - T_ref))
    pmax_stc= pmax_meas* (G_ref/irr_model) / (1 + TK_Pmax*(T_cell - T_ref))
    jsc     = isc / MODULE_AREA_M2            (aperture current density)
  LOGIC: scale current/power by the irradiance ratio onto 1000 W/m^2, then
  divide out the temperature coefficient onto 25 C. Voc gets only the
  temperature term (irradiance-insensitive to first order).

DEGRADATION VIEW
    actual          = the STC-corrected value over time
    change-from-base = 100 * (X(t) - X0) / X0, where X0 is the module's
                       earliest STC-corrected value. Removes module-to-module
                       offset so only the drift over time remains.
------------------------------------------------------------------------------

Run from repo root:
    python src/plotting/plot_module_timeseries.py
    python src/plotting/plot_module_timeseries.py <workbook.xlsx> <bay> <out_dir>
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

# FS-7520A aperture area (m^2). Used to form Jsc = Isc / area. Note: for a
# series-connected module this is aperture current density, not cell Jsc;
# percent-change in Jsc equals percent-change in Isc regardless of area.
MODULE_AREA_M2 = 2.80


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
    # Jsc (aperture current density), measured and corrected
    area = MODULE_AREA_M2 if MODULE_AREA_M2 else 1.0
    m["jsc_meas"] = m["isc_meas_a"] / area
    m["jsc_stc"] = m["isc_stc"] / area
    return m


JSC_LAB = "Jsc (A/m^2)" if MODULE_AREA_M2 else "Isc (A)"


def _modules(sub):
    mods = sorted(sub["module"].unique())
    return mods, dict(zip(mods, plt.cm.tab10.colors))


def _date_axis(ax):
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))


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
    for a in ax:
        _date_axis(a)
        a.legend(fontsize=8, ncol=4, loc="best")
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
    axes[0, 1].legend(fontsize=8, ncol=2, loc="best")
    for c in range(2):
        axes[-1, c].set_xlabel("Date")
    fig.suptitle(f"Bay {bay} - measured vs STC-corrected (grouped by module; OC vs SC)",
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

    rows = [("pmax_stc", "Pmp (W)"),
            ("voc_stc", "Voc (V)"),
            ("jsc_stc", JSC_LAB)]

    fig, axes = plt.subplots(len(rows), 2, figsize=(13, 11), sharex=True)
    for r, (col, ylab) in enumerate(rows):
        axL, axR = axes[r, 0], axes[r, 1]
        for k in mods:
            d = sub[sub["module"] == k].sort_values("datetime_local")
            axL.plot(d["datetime_local"], d[col], "o-", ms=4, lw=1.1,
                     color=colors[k], label=k, alpha=0.85)
            base = d[col].iloc[0]
            pct = 100.0 * (d[col] - base) / base
            axR.plot(d["datetime_local"], pct, "o-", ms=4, lw=1.1,
                     color=colors[k], label=k, alpha=0.85)
        axR.axhline(0, color="k", lw=0.8, ls="--", alpha=0.5)
        axL.set_ylabel(ylab)
        axR.set_ylabel("change (%)")
        name = ylab.split("(")[0].strip()
        axL.set_title(f"{name} - actual (STC)", fontsize=10)
        axR.set_title(f"{name} - change from first measurement (%)", fontsize=10)
        _date_axis(axL); _date_axis(axR)
    axes[0, 0].legend(fontsize=8, ncol=2, loc="best")
    for c in range(2):
        axes[-1, c].set_xlabel("Date")
    fig.suptitle(f"Bay {bay} - degradation view: actual STC values and change from baseline",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def main(workbook, bay, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    df = load_and_correct(workbook)
    f1 = plot_pf_ff(df, bay, os.path.join(out_dir, f"fig_timeseries_bay{bay}.png"))
    f2 = plot_corrections(df, bay, os.path.join(out_dir, f"fig_corrections_bay{bay}.png"))
    f3 = plot_degradation(df, bay, os.path.join(out_dir, f"fig_degradation_bay{bay}.png"))
    for f in (f1, f2, f3):
        print("Wrote", f)


if __name__ == "__main__":
    workbook = sys.argv[1] if len(sys.argv) > 1 else "outputs/master_iv_workbook.xlsx"
    bay = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "outputs"
    main(workbook, bay, out_dir)
