from pathlib import Path
import argparse
import pandas as pd
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_qc_corrected.csv"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "fitted_parameters" / "correction_effectiveness_summary.csv"


def safe_divide(a, b):
    return np.where((b != 0) & (~pd.isna(b)), a / b, np.nan)


def linear_fit_summary(df, x_col, y_col):
    sub = df[[x_col, y_col]].dropna()

    if len(sub) < 2:
        return {
            "x_col": x_col,
            "y_col": y_col,
            "n_points": len(sub),
            "slope": np.nan,
            "intercept": np.nan,
            "r_squared": np.nan,
        }

    x = sub[x_col].to_numpy(dtype=float)
    y = sub[y_col].to_numpy(dtype=float)

    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept

    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)

    r_squared = 1.0 - ss_res / ss_tot if ss_tot != 0 else np.nan

    return {
        "x_col": x_col,
        "y_col": y_col,
        "n_points": len(sub),
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
    }


def add_fill_factor_columns(df):
    df["ff_measured"] = safe_divide(
        df["measured_pmax"],
        df["measured_voc"] * df["measured_isc"],
    )

    df["ff_measured_percent"] = 100.0 * df["ff_measured"]

    df["pmax_reconstructed_from_corrected_voc_isc_and_raw_ff"] = (
        df["voc_datasheet_corr_v"]
        * df["isc_datasheet_corr_a"]
        * df["ff_measured"]
    )

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Quantify whether first-order CdTe corrections reduce environmental dependence."
    )

    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--exclude-qc-flagged", action="store_true")

    args = parser.parse_args()

    df = pd.read_csv(args.input)

    if args.exclude_qc_flagged and "qc_any_flag" in df.columns:
        df = df[df["qc_any_flag"] == False].copy()

    df = add_fill_factor_columns(df)

    tests = [
        ("irradiance_w_m2", "measured_pmax"),
        ("irradiance_w_m2", "pmax_datasheet_corr_w"),
        ("temperature_c", "measured_pmax"),
        ("temperature_c", "pmax_datasheet_corr_w"),
        ("temperature_c", "measured_voc"),
        ("temperature_c", "voc_datasheet_corr_v"),
        ("irradiance_w_m2", "measured_isc"),
        ("irradiance_w_m2", "isc_datasheet_corr_a"),
        ("temperature_c", "ff_measured"),
        ("irradiance_w_m2", "ff_measured"),
        ("irradiance_w_m2", "pmax_reconstructed_from_corrected_voc_isc_and_raw_ff"),
        ("temperature_c", "pmax_reconstructed_from_corrected_voc_isc_and_raw_ff"),
    ]

    rows = []

    for x_col, y_col in tests:
        if x_col in df.columns and y_col in df.columns:
            rows.append(linear_fit_summary(df, x_col, y_col))

    summary = pd.DataFrame(rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    print()
    print("CORRECTION EFFECTIVENESS SUMMARY")
    print("--------------------------------")
    print(summary.to_string(index=False))
    print()
    print("Fill factor range:")
    print(f"FF min  = {df['ff_measured_percent'].min():.2f} %")
    print(f"FF mean = {df['ff_measured_percent'].mean():.2f} %")
    print(f"FF max  = {df['ff_measured_percent'].max():.2f} %")
    print()
    print("Saved summary to:")
    print(output_path)


if __name__ == "__main__":
    main()