#!/usr/bin/env python3
"""
parse_iv_master.py  --  src/io/

Parse Solmetric PVA v3.0 CSV exports into tidy dataframes for the master workbook.

Public API:
    parse_directory(data_dir, recursive=True) -> (master_df, iv_points_df)
    parse_file(path)                          -> (row_dict, iv_points_df)

Identity (bay / module / config / quality) and datetime are read from the
file *contents* (Array Location + Measurement Date/Time), not the filenames,
which are inconsistent across bays. '=NA()' is treated as missing.
"""
import os
import re
import glob
import datetime as dt
import numpy as np
import pandas as pd

NA_TOKENS = {"=NA()", "NA", "", "nan", "NaN"}
MEAS_KEYS = ("Pmax", "Vmpp", "Impp", "Voc", "Isc")


def _num(x):
    if x is None:
        return np.nan
    s = str(x).strip().strip('"')
    if s in NA_TOKENS:
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def _clean(x):
    return str(x).strip().strip('"') if x is not None else ""


def parse_array_location(loc, note):
    loc = _clean(loc)
    out = {"array_location": loc, "bay": np.nan, "module_id": None,
           "config": None, "quality": None, "loc_tag": None}
    m = re.search(r"Bay\s*(\d+)", loc, re.I)
    if m:
        out["bay"] = int(m.group(1))
    m = re.search(r"\(([^)]*)\)", loc)
    if m:
        tag = m.group(1).strip().lower()
        out["loc_tag"] = tag
        if any(t in tag for t in ("bad", "good", "fav")):
            out["quality"] = tag
    cfg = None
    m = re.search(r"\bMod\s*\d+\s*(OC|SC)\b", loc, re.I)
    if m:
        cfg = m.group(1).upper()
    else:
        m = re.search(r"\b(OC|SC)\b", note, re.I)
        if m:
            cfg = m.group(1).upper()
    out["config"] = cfg
    m = re.search(r"Mod\s*(\d+)", loc, re.I)
    if m:
        out["module_id"] = f"Mod{m.group(1)}"
    else:
        m = re.search(r"-\s*(\d+)\s*$", loc)
        if m:
            out["module_id"] = m.group(1)
    return out


def parse_datetime(date_str, time_str):
    date_str, time_str = _clean(date_str), _clean(time_str)
    if not date_str or date_str in NA_TOKENS:
        return None, np.nan
    gmt = re.search(r"GMT([+-]\d+)", time_str)
    tz_off = int(gmt.group(1)) if gmt else None
    clock = re.sub(r"\(.*?\)", "", time_str).strip()
    parsed = None
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p"):
        try:
            parsed = dt.datetime.strptime(f"{date_str} {clock}", fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = dt.datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            return None, tz_off
    return parsed, tz_off  # naive local clock + offset


def module_label(bay, module_id, config):
    if pd.isna(bay):
        return module_id or "?"
    cfg = f"-{config}" if isinstance(config, str) and config else ""
    return f"B{int(bay)} {module_id}{cfg}"


def parse_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [ln.rstrip("\r\n") for ln in fh.read().split("\n")]

    meta, meas, model, iv_start = {}, {}, {}, None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("IV Measurements"):
            iv_start = i
            break
        cells = ln.split(",")
        key = _clean(cells[0]) if cells else ""
        if key in MEAS_KEYS:
            meas[key] = _num(cells[1]) if len(cells) > 1 else np.nan
            model[key] = _num(cells[2]) if len(cells) > 2 else np.nan
        elif key and len(cells) > 1 and key not in meta:
            meta[key] = cells[1]

    volts, amps, watts = [], [], []
    if iv_start is not None:
        for ln in lines[iv_start + 1:]:
            cells = ln.split(",")
            if len(cells) < 3 or _clean(cells[0]).upper() == "VOLTS":
                continue
            v, a = _num(cells[0]), _num(cells[1])
            if np.isnan(v) or np.isnan(a):
                continue
            w = _num(cells[2])
            watts.append(w if not np.isnan(w) else v * a)
            volts.append(v); amps.append(a)

    note = _clean(meta.get("Measurement Note", ""))
    ident = parse_array_location(meta.get("Array Location", ""), note)
    when, tz_off = parse_datetime(meta.get("Measurement Date", ""),
                                  meta.get("Measurement Time", ""))
    g = lambda k: _num(meta.get(k))

    row = {
        "file": os.path.basename(path),
        "module": module_label(ident["bay"], ident["module_id"], ident["config"]),
        "datetime_local": when,
        "tz_offset_hr": tz_off,
        **ident,
        "note": note,
        "module_model": _clean(meta.get("Module Model", "")),
        "project_file": _clean(meta.get("Project File", "")),
        "pmax_meas_w": meas.get("Pmax"), "vmpp_meas_v": meas.get("Vmpp"),
        "impp_meas_a": meas.get("Impp"), "voc_meas_v": meas.get("Voc"),
        "isc_meas_a": meas.get("Isc"),
        "pmax_model_w": model.get("Pmax"), "vmpp_model_v": model.get("Vmpp"),
        "impp_model_a": model.get("Impp"), "voc_model_v": model.get("Voc"),
        "isc_model_a": model.get("Isc"),
        "irr_solsensor_wm2": g("Irradiance (W/m^2)"),
        "temp_tc1_c": g("Temperature Thermocouple 1 (Deg C)"),
        "temp_tc2_c": g("Temperature Thermocouple 2 (Deg C)"),
        "tilt_meas_deg": g("Tilt (from pitch and roll above) (Deg)"),
        "irr_model_wm2": g("Irradiance used in model (W/m^2)"),
        "cell_temp_model_c": g("Cell Temperature used in model (Deg C)"),
        "aoi_deg": g("AOI (degrees)"),
        "array_azimuth_deg": g("Array Azimuth (Deg)"),
        "user_series_r_ohm": g("User Series R (Ohms)"),
        "performance_factor_pct": g("Performance Factor (%)"),
        "n_iv_points": len(volts),
    }
    iv = pd.DataFrame({"file": os.path.basename(path),
                       "module": row["module"],
                       "v": volts, "i": amps, "p": watts})
    return row, iv


def parse_directory(data_dir, recursive=True):
    pat = os.path.join(data_dir, "**", "*.csv") if recursive \
        else os.path.join(data_dir, "*.csv")
    files = sorted(glob.glob(pat, recursive=recursive))
    rows, ivs, errors = [], [], []
    for p in files:
        try:
            r, iv = parse_file(p)
            rows.append(r)
            if len(iv):
                ivs.append(iv)
        except Exception as e:  # noqa
            errors.append((os.path.basename(p), repr(e)))

    master = pd.DataFrame(rows)
    if len(master):
        master = master.sort_values(
            ["bay", "module_id", "config", "datetime_local"]).reset_index(drop=True)
        master.insert(0, "meas_id", range(1, len(master) + 1))
    iv_all = pd.concat(ivs, ignore_index=True) if ivs else pd.DataFrame()
    if len(iv_all):
        fid = dict(zip(master["file"], master["meas_id"]))
        iv_all.insert(0, "meas_id", iv_all["file"].map(fid))
    if errors:
        print(f"[parse_iv_master] {len(errors)} parse error(s):")
        for f, e in errors:
            print("   ", f, e)
    return master, iv_all


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "data/raw_iv_traces"
    m, iv = parse_directory(d)
    print(f"Parsed {len(m)} measurements, {len(iv)} IV points from {d}")