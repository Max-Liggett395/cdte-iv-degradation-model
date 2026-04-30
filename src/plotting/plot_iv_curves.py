from pathlib import Path
import argparse
import pandas as pd
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_METADATA = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_summary.csv"
DEFAULT_FIGURE_DIR = REPO_ROOT / "outputs" / "figures"


def plot_module_iv_curves(metadata_csv, figure_dir, module_id=None):
    metadata_csv = Path(metadata_csv)
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(metadata_csv)

    if module_id is not None:
        df = df[df["folder_module_id"].astype(str) == str(module_id)]

    if df.empty:
        print("No matching metadata rows found.")
        return

    for mod_id, group in df.groupby("folder_module_id"):
        group = group.sort_values("filename_datetime_local")

        plt.figure(figsize=(8, 6))

        for _, row in group.iterrows():
            iv_file = Path(row["clean_iv_output_file"])

            if not iv_file.exists():
                print(f"Missing IV file: {iv_file}")
                continue

            iv = pd.read_csv(iv_file)

            label = (
                f"{row.get('filename_date', '')} "
                f"Pmax={row.get('measured_pmax', float('nan')):.1f} W"
            )

            plt.plot(iv["voltage_v"], iv["current_a"], marker="o", markersize=2, linewidth=1, label=label)

        plt.xlabel("Voltage (V)")
        plt.ylabel("Current (A)")
        plt.title(f"IV Curves - Module {mod_id}")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.tight_layout()

        out = figure_dir / f"module_{mod_id}_iv_overlay.png"
        plt.savefig(out, dpi=300)
        plt.close()

        print(f"Saved: {out}")


def plot_module_power_curves(metadata_csv, figure_dir, module_id=None):
    metadata_csv = Path(metadata_csv)
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(metadata_csv)

    if module_id is not None:
        df = df[df["folder_module_id"].astype(str) == str(module_id)]

    if df.empty:
        print("No matching metadata rows found.")
        return

    for mod_id, group in df.groupby("folder_module_id"):
        group = group.sort_values("filename_datetime_local")

        plt.figure(figsize=(8, 6))

        for _, row in group.iterrows():
            iv_file = Path(row["clean_iv_output_file"])

            if not iv_file.exists():
                print(f"Missing IV file: {iv_file}")
                continue

            iv = pd.read_csv(iv_file)

            label = (
                f"{row.get('filename_date', '')} "
                f"Pmax={row.get('measured_pmax', float('nan')):.1f} W"
            )

            plt.plot(iv["voltage_v"], iv["power_w"], marker="o", markersize=2, linewidth=1, label=label)

        plt.xlabel("Voltage (V)")
        plt.ylabel("Power (W)")
        plt.title(f"Power Curves - Module {mod_id}")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.tight_layout()

        out = figure_dir / f"module_{mod_id}_power_overlay.png"
        plt.savefig(out, dpi=300)
        plt.close()

        print(f"Saved: {out}")


def plot_parameter_trends(metadata_csv, figure_dir, module_id=None):
    metadata_csv = Path(metadata_csv)
    figure_dir = Path(figure_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(metadata_csv)
    df["datetime"] = pd.to_datetime(df["filename_datetime_local"], errors="coerce")

    if module_id is not None:
        df = df[df["folder_module_id"].astype(str) == str(module_id)]

    parameters = [
        ("measured_pmax", "Pmax (W)"),
        ("measured_voc", "Voc (V)"),
        ("measured_isc", "Isc (A)"),
        ("measured_vmpp", "Vmpp (V)"),
        ("measured_impp", "Impp (A)"),
        ("solsensor_irradiance", "Irradiance (W/m²)"),
        ("solsensor_temperature_thermocouple_1", "Temperature TC1 (°C)"),
    ]

    for parameter, ylabel in parameters:
        if parameter not in df.columns:
            print(f"Skipping missing column: {parameter}")
            continue

        plt.figure(figsize=(9, 6))

        for mod_id, group in df.groupby("folder_module_id"):
            group = group.sort_values("datetime")
            plt.plot(group["datetime"], group[parameter], marker="o", linewidth=1, label=f"Module {mod_id}")

        plt.xlabel("Measurement Date")
        plt.ylabel(ylabel)
        plt.title(f"{ylabel} Over Time")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.xticks(rotation=45)
        plt.tight_layout()

        suffix = f"_module_{module_id}" if module_id is not None else "_all_modules"
        out = figure_dir / f"{parameter}{suffix}.png"
        plt.savefig(out, dpi=300)
        plt.close()

        print(f"Saved: {out}")


def main():
    parser = argparse.ArgumentParser(description="Plot IV curves and basic metadata trends.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA))
    parser.add_argument("--figure-dir", default=str(DEFAULT_FIGURE_DIR))
    parser.add_argument("--module-id", default=None, help="Optional module ID, e.g. 114")

    args = parser.parse_args()

    plot_module_iv_curves(args.metadata, args.figure_dir, args.module_id)
    plot_module_power_curves(args.metadata, args.figure_dir, args.module_id)
    plot_parameter_trends(args.metadata, args.figure_dir, args.module_id)


if __name__ == "__main__":
    main()