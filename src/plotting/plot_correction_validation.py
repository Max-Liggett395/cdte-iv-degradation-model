from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_qc_corrected.csv"
DEFAULT_FIGURE_DIR = REPO_ROOT / "outputs" / "figures"


def scatter_raw_vs_corrected(df, x_col, raw_y_col, corr_y_col, x_label, y_label, title, output_path):
    plt.figure(figsize=(8, 6))

    plt.scatter(df[x_col], df[raw_y_col], marker="o", label="Raw")
    plt.scatter(df[x_col], df[corr_y_col], marker="s", label="Corrected")

    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Saved: {output_path}")


def plot_module_colored_scatter(df, x_col, y_col, x_label, y_label, title, output_path):
    plt.figure(figsize=(8, 6))

    for module_id, group in df.groupby("module_id"):
        plt.scatter(group[x_col], group[y_col], label=f"Module {module_id}")

    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend(fontsize=8)
    plt.tight_layout()

    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate whether CdTe correction reduces irradiance and temperature dependence."
    )

    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--figure-dir", default=str(DEFAULT_FIGURE_DIR))
    parser.add_argument(
        "--exclude-qc-flagged",
        action="store_true",
        help="Exclude rows where qc_any_flag is True.",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    figure_dir = Path(args.figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)

    if args.exclude_qc_flagged and "qc_any_flag" in df.columns:
        df = df[df["qc_any_flag"] == False].copy()

    required_cols = [
        "module_id",
        "irradiance_w_m2",
        "temperature_c",
        "measured_pmax",
        "pmax_datasheet_corr_w",
        "measured_voc",
        "voc_datasheet_corr_v",
        "measured_isc",
        "isc_datasheet_corr_a",
    ]

    missing = [col for col in required_cols if col not in df.columns]

    if missing:
        raise ValueError(
            "Missing required columns. Re-run qc_and_correct_metadata.py first. Missing: "
            + ", ".join(missing)
        )

    # Raw vs corrected environmental dependence checks
    scatter_raw_vs_corrected(
        df=df,
        x_col="irradiance_w_m2",
        raw_y_col="measured_pmax",
        corr_y_col="pmax_datasheet_corr_w",
        x_label="Irradiance (W/m²)",
        y_label="Pmax (W)",
        title="Pmax vs Irradiance: Raw vs Datasheet-Corrected",
        output_path=figure_dir / "validation_pmax_vs_irradiance_raw_vs_corrected.png",
    )

    scatter_raw_vs_corrected(
        df=df,
        x_col="temperature_c",
        raw_y_col="measured_pmax",
        corr_y_col="pmax_datasheet_corr_w",
        x_label="Temperature TC1 (°C)",
        y_label="Pmax (W)",
        title="Pmax vs Temperature: Raw vs Datasheet-Corrected",
        output_path=figure_dir / "validation_pmax_vs_temperature_raw_vs_corrected.png",
    )

    scatter_raw_vs_corrected(
        df=df,
        x_col="temperature_c",
        raw_y_col="measured_voc",
        corr_y_col="voc_datasheet_corr_v",
        x_label="Temperature TC1 (°C)",
        y_label="Voc (V)",
        title="Voc vs Temperature: Raw vs Datasheet-Corrected",
        output_path=figure_dir / "validation_voc_vs_temperature_raw_vs_corrected.png",
    )

    scatter_raw_vs_corrected(
        df=df,
        x_col="irradiance_w_m2",
        raw_y_col="measured_isc",
        corr_y_col="isc_datasheet_corr_a",
        x_label="Irradiance (W/m²)",
        y_label="Isc (A)",
        title="Isc vs Irradiance: Raw vs Datasheet-Corrected",
        output_path=figure_dir / "validation_isc_vs_irradiance_raw_vs_corrected.png",
    )

    # Module-colored corrected diagnostic plots
    plot_module_colored_scatter(
        df=df,
        x_col="irradiance_w_m2",
        y_col="pmax_datasheet_corr_w",
        x_label="Irradiance (W/m²)",
        y_label="Datasheet-Corrected Pmax (W)",
        title="Corrected Pmax vs Irradiance by Module",
        output_path=figure_dir / "validation_corrected_pmax_vs_irradiance_by_module.png",
    )

    plot_module_colored_scatter(
        df=df,
        x_col="temperature_c",
        y_col="pmax_datasheet_corr_w",
        x_label="Temperature TC1 (°C)",
        y_label="Datasheet-Corrected Pmax (W)",
        title="Corrected Pmax vs Temperature by Module",
        output_path=figure_dir / "validation_corrected_pmax_vs_temperature_by_module.png",
    )

    plot_module_colored_scatter(
        df=df,
        x_col="temperature_c",
        y_col="voc_datasheet_corr_v",
        x_label="Temperature TC1 (°C)",
        y_label="Datasheet-Corrected Voc (V)",
        title="Corrected Voc vs Temperature by Module",
        output_path=figure_dir / "validation_corrected_voc_vs_temperature_by_module.png",
    )

    print()
    print("Correction validation plots created.")
    print("Inspect whether corrected values still show strong dependence on irradiance or temperature.")


if __name__ == "__main__":
    main()