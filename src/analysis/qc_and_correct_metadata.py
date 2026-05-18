from pathlib import Path
import argparse
import pandas as pd
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_summary.csv"
DEFAULT_OUTPUT = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_qc_corrected.csv"


# -----------------------------
# USER-ADJUSTABLE CdTe SETTINGS
# -----------------------------
G_REF = 1000.0          # W/m^2
T_REF = 25.0            # deg C

# First Solar Series 7 TR1 datasheet-style relative temperature coefficients.
# These are relative coefficients in units of 1/deg C.
ALPHA_ISC_REL_PER_C = 0.0004      # +0.04 %/deg C
BETA_VOC_REL_PER_C = -0.0028      # -0.28 %/deg C
GAMMA_PMAX_REL_PER_C = -0.0032    # -0.32 %/deg C

G_MIN_VALID = 700.0               # minimum irradiance threshold for good outdoor IV trace


def safe_divide(a, b):
    return np.where((b != 0) & (~pd.isna(b)), a / b, np.nan)


def add_canonical_columns(df):
    """
    Create consistent columns that future scripts can rely on.
    Original parser columns are preserved.
    """
    df["module_id"] = df["folder_module_id"].astype(str)
    df["bay"] = df["folder_bay"].astype(str)
    df["bay_number"] = df["folder_bay_number"]
    df["bay_condition"] = df["folder_bay_condition"]

    df["datetime"] = pd.to_datetime(df["filename_datetime_local"], errors="coerce")

    df["irradiance_w_m2"] = pd.to_numeric(df["solsensor_irradiance"], errors="coerce")
    df["temperature_c"] = pd.to_numeric(df["solsensor_temperature_thermocouple_1"], errors="coerce")

    for col in [
        "measured_pmax",
        "measured_voc",
        "measured_isc",
        "measured_vmpp",
        "measured_impp",
        "parsed_max_power_w",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def add_qc_flags(df):
    """
    Add basic quality-control flags.
    A True flag means that row has that specific issue.
    """
    df["qc_missing_datetime"] = df["datetime"].isna()
    df["qc_missing_irradiance"] = df["irradiance_w_m2"].isna()
    df["qc_missing_temperature"] = df["temperature_c"].isna()

    df["qc_low_irradiance"] = df["irradiance_w_m2"] < G_MIN_VALID

    df["qc_missing_core_electrical"] = (
        df["measured_pmax"].isna()
        | df["measured_voc"].isna()
        | df["measured_isc"].isna()
        | df["measured_vmpp"].isna()
        | df["measured_impp"].isna()
    )

    df["qc_module_id_mismatch"] = (
        df["folder_module_id"].astype(str) != df["filename_module_id"].astype(str)
    )

    df["pmax_difference_parsed_minus_reported_w"] = (
        df["parsed_max_power_w"] - df["measured_pmax"]
    )

    df["pmax_difference_percent"] = (
        100.0
        * safe_divide(
            df["pmax_difference_parsed_minus_reported_w"],
            df["measured_pmax"],
        )
    )

    df["qc_large_pmax_parse_difference"] = df["pmax_difference_percent"].abs() > 1.0

    duplicate_subset = ["module_id", "datetime"]
    df["qc_duplicate_module_datetime"] = df.duplicated(subset=duplicate_subset, keep=False)

    qc_cols = [
        "qc_missing_datetime",
        "qc_missing_irradiance",
        "qc_missing_temperature",
        "qc_low_irradiance",
        "qc_missing_core_electrical",
        "qc_module_id_mismatch",
        "qc_large_pmax_parse_difference",
        "qc_duplicate_module_datetime",
    ]

    df["qc_any_flag"] = df[qc_cols].any(axis=1)

    return df


def add_simple_cdte_corrections(df):
    """
    Add first-pass CdTe correction/normalization columns using measured
    thermocouple temperature and datasheet-style relative coefficients.

    These corrections are not intended to replace IEC 60891-style translation
    or full diode-model fitting. They are intended to provide corrected
    comparison metrics that can later be used alongside diode-model results.
    """

    G = df["irradiance_w_m2"]
    T = df["temperature_c"]

    # Irradiance-normalized Isc using measured thermocouple temperature.
    # Isc_ref = Isc_meas * (G_ref/G) / (1 + alpha*(T - T_ref))
    df["isc_datasheet_corr_a"] = (
        df["measured_isc"]
        * safe_divide(G_REF, G)
        / (1.0 + ALPHA_ISC_REL_PER_C * (T - T_REF))
    )

    # Temperature-corrected Voc using relative datasheet coefficient.
    # Voc_ref = Voc_meas / (1 + beta*(T - T_ref))
    df["voc_datasheet_corr_v"] = (
        df["measured_voc"]
        / (1.0 + BETA_VOC_REL_PER_C * (T - T_REF))
    )

    # Datasheet-style Pmax correction using irradiance and Pmax temperature coefficient.
    # Pmax_ref = Pmax_meas / [(G/G_ref) * (1 + gamma*(T - T_ref))]
    df["pmax_datasheet_corr_w"] = (
        df["measured_pmax"]
        / (
            safe_divide(G, G_REF)
            * (1.0 + GAMMA_PMAX_REL_PER_C * (T - T_REF))
        )
    )

    # Backward-compatible names used by earlier plotting scripts.
    # These names allow old plotting scripts to keep working.
    df["isc_norm_a"] = df["isc_datasheet_corr_a"]
    df["voc_temp_corr_v"] = df["voc_datasheet_corr_v"]
    df["pmax_irradiance_norm_w"] = df["measured_pmax"] * safe_divide(G_REF, G)

    # Older simple correction kept for comparison only.
    # Prefer pmax_datasheet_corr_w for future analysis.
    df["pmax_simple_corr_w"] = (
        df["measured_pmax"]
        * safe_divide(G_REF, G)
        * safe_divide(df["voc_datasheet_corr_v"], df["measured_voc"])
    )

    return df


def print_summary(df):
    print()
    print("QC SUMMARY")
    print("----------")
    print(f"Rows: {len(df)}")
    print(f"Modules: {df['module_id'].nunique()}")
    print(f"Bays: {df['bay'].nunique()}")
    print()

    qc_cols = [col for col in df.columns if col.startswith("qc_")]

    for col in qc_cols:
        print(f"{col}: {int(df[col].sum())}")

    print()
    print("Measurement ranges")
    print("------------------")
    for col in [
        "measured_pmax",
        "measured_voc",
        "measured_isc",
        "irradiance_w_m2",
        "temperature_c",
        "isc_datasheet_corr_a",
        "voc_datasheet_corr_v",
        "pmax_datasheet_corr_w",
        "pmax_simple_corr_w",
    ]:
        if col in df.columns:
            print(
                f"{col}: "
                f"min={df[col].min():.3f}, "
                f"mean={df[col].mean():.3f}, "
                f"max={df[col].max():.3f}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Add QC flags and CdTe correction columns to parsed IV metadata."
    )

    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)

    df = add_canonical_columns(df)
    df = add_qc_flags(df)
    df = add_simple_cdte_corrections(df)

    df.to_csv(output_path, index=False)

    print_summary(df)
    print()
    print("Saved corrected metadata to:")
    print(output_path)


if __name__ == "__main__":
    main()