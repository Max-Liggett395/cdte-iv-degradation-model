from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INPUT = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_qc_corrected.csv"
DEFAULT_FIGURE_DIR = REPO_ROOT / "outputs" / "figures"


PLOT_PAIRS = [
    ("measured_pmax", "pmax_simple_corr_w", "Pmax", "Power (W)"),
    ("measured_voc", "voc_temp_corr_v", "Voc", "Voltage (V)"),
    ("measured_isc", "isc_norm_a", "Isc", "Current (A)"),
]


def plot_raw_vs_corrected(df, figure_dir, module_id=None):
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    if module_id is not None:
        df = df[df["module_id"].astype(str) == str(module_id)]

    for raw_col, corr_col, title_name, ylabel in PLOT_PAIRS:
        plt.figure(figsize=(9, 6))

        for mod_id, group in df.groupby("module_id"):
            group = group.sort_values("datetime")

            plt.plot(
                group["datetime"],
                group[raw_col],
                marker="o",
                linestyle="-",
                linewidth=1,
                label=f"Module {mod_id} raw",
            )

            plt.plot(
                group["datetime"],
                group[corr_col],
                marker="s",
                linestyle="--",
                linewidth=1,
                label=f"Module {mod_id} corrected",
            )

        plt.xlabel("Measurement Date")
        plt.ylabel(ylabel)
        plt.title(f"Raw vs Corrected {title_name}")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=7)
        plt.xticks(rotation=45)
        plt.tight_layout()

        suffix = f"module_{module_id}" if module_id is not None else "all_modules"
        out = figure_dir / f"raw_vs_corrected_{title_name.lower()}_{suffix}.png"
        plt.savefig(out, dpi=300)
        plt.close()

        print(f"Saved: {out}")


def plot_corrected_only(df, figure_dir, module_id=None):
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")

    if module_id is not None:
        df = df[df["module_id"].astype(str) == str(module_id)]

    corrected_cols = [
        ("pmax_simple_corr_w", "Corrected Pmax (W)"),
        ("voc_temp_corr_v", "Corrected Voc (V)"),
        ("isc_norm_a", "Normalized Isc (A)"),
        ("pmax_irradiance_norm_w", "Irradiance-Normalized Pmax (W)"),
    ]

    for col, ylabel in corrected_cols:
        plt.figure(figsize=(9, 6))

        for mod_id, group in df.groupby("module_id"):
            group = group.sort_values("datetime")
            plt.plot(group["datetime"], group[col], marker="o", linewidth=1, label=f"Module {mod_id}")

        plt.xlabel("Measurement Date")
        plt.ylabel(ylabel)
        plt.title(f"{ylabel} Over Time")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.xticks(rotation=45)
        plt.tight_layout()

        suffix = f"module_{module_id}" if module_id is not None else "all_modules"
        out = figure_dir / f"{col}_{suffix}.png"
        plt.savefig(out, dpi=300)
        plt.close()

        print(f"Saved: {out}")


def main():
    parser = argparse.ArgumentParser(description="Plot raw vs corrected IV metadata trends.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--figure-dir", default=str(DEFAULT_FIGURE_DIR))
    parser.add_argument("--module-id", default=None)

    args = parser.parse_args()

    df = pd.read_csv(args.input)

    plot_raw_vs_corrected(df, args.figure_dir, args.module_id)
    plot_corrected_only(df, args.figure_dir, args.module_id)


if __name__ == "__main__":
    main()