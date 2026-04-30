from pathlib import Path
import csv
import re
import argparse
from datetime import datetime


# -----------------------------
# DEFAULT PROJECT PATHS
# -----------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw_iv_traces"
DEFAULT_PROCESSED_DIR = REPO_ROOT / "data" / "processed_iv_traces"
DEFAULT_METADATA_OUT = REPO_ROOT / "outputs" / "fitted_parameters" / "iv_metadata_summary.csv"


# -----------------------------
# HELPERS
# -----------------------------
def clean_key(text):
    """Convert messy CSV field names into clean snake_case keys."""
    text = str(text).strip()
    text = text.replace("#", "number")
    text = text.replace("%", "percent")
    text = text.replace("^", "")
    text = text.replace("/", "_per_")
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = text.strip("_").lower()
    return text


def parse_float(value):
    """Safely convert numeric text to float; return None for NA/formulas/text."""
    if value is None:
        return None

    value = str(value).strip()

    if value == "" or value.upper() in {"NA", "N/A", "NONE"}:
        return None

    if value.startswith("="):
        return None

    try:
        return float(value)
    except ValueError:
        return value


def safe_filename(text):
    """Make a safe filename stem."""
    text = str(text).strip()
    text = re.sub(r"[^\w\-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def parse_filename_metadata(file_path):
    """
    Parse filenames like:
    Bay 2_114 3-17-2026 10-56-15 AM (GMT-6).csv
    Bay 2 (bad)-114 3-4-2026 03-38-04 PM (GMT-7).csv
    """
    stem = file_path.stem

    # Remove duplicate Windows copy suffixes like "(1)" at end
    stem_clean = re.sub(r"\(\d+\)$", "", stem).strip()

    pattern = re.compile(
        r"""
        (?P<bay_label>Bay\s*\d+(?:\s*\(bad\))?)
        [\s_\-]+
        (?P<module_id>\d{3})
        [\s_\-]+
        (?P<date>\d{1,2}-\d{1,2}-\d{4})
        \s+
        (?P<time>\d{1,2}-\d{2}-\d{2})
        \s+
        (?P<ampm>AM|PM)
        \s+
        \((?P<gmt>GMT[+-]\d+)\)
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    match = pattern.search(stem_clean)

    metadata = {
        "filename_stem": stem,
        "filename_stem_clean": stem_clean,
        "filename_bay_label": None,
        "filename_module_id": None,
        "filename_date": None,
        "filename_time": None,
        "filename_gmt_offset": None,
        "filename_datetime_local": None,
    }

    if not match:
        return metadata

    bay_label = match.group("bay_label")
    module_id = match.group("module_id")
    date_text = match.group("date")
    time_text = match.group("time").replace("-", ":")
    ampm = match.group("ampm").upper()
    gmt = match.group("gmt").upper()

    metadata["filename_bay_label"] = bay_label
    metadata["filename_module_id"] = module_id
    metadata["filename_date"] = date_text
    metadata["filename_time"] = f"{time_text} {ampm}"
    metadata["filename_gmt_offset"] = gmt

    try:
        dt = datetime.strptime(f"{date_text} {time_text} {ampm}", "%m-%d-%Y %I:%M:%S %p")
        metadata["filename_datetime_local"] = dt.isoformat()
    except ValueError:
        pass

    return metadata


def infer_folder_metadata(file_path, raw_root):
    """Infer bay folder and module folder from path structure."""
    rel = file_path.relative_to(raw_root)
    parts = rel.parts

    bay_folder = parts[0] if len(parts) >= 2 else None
    module_folder = parts[1] if len(parts) >= 3 else None

    metadata = {
        "relative_raw_path": str(rel),
        "folder_bay": bay_folder,
        "folder_module_id": module_folder,
    }

    if bay_folder:
        bay_match = re.search(r"bay[_\s]*(\d+)", bay_folder, re.IGNORECASE)
        metadata["folder_bay_number"] = bay_match.group(1) if bay_match else None
        metadata["folder_bay_condition"] = "bad" if "bad" in bay_folder.lower() else "normal"
    else:
        metadata["folder_bay_number"] = None
        metadata["folder_bay_condition"] = None

    return metadata


# -----------------------------
# CORE PARSER
# -----------------------------
def parse_fluke_pva_csv(file_path, raw_root):
    """
    Parse one Solmetric/Fluke PVA CSV file.

    Returns:
        metadata: dict
        iv_rows: list of dicts with voltage, current, power
    """

    metadata = {
        "source_file": str(file_path),
        "source_filename": file_path.name,
    }

    metadata.update(infer_folder_metadata(file_path, raw_root))
    metadata.update(parse_filename_metadata(file_path))

    iv_rows = []
    section = "header"

    with open(file_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)

        for row in reader:
            row = [cell.strip() for cell in row]

            if not row or all(cell == "" for cell in row):
                continue

            first = row[0].strip()

            # Detect sections
            if first.upper() == "IV MEASUREMENTS:":
                section = "iv_marker"
                continue

            if first.upper() == "VOLTS":
                section = "iv_data"
                continue

            if first.upper() == "SOLSENSOR MEASUREMENTS":
                section = "solsensor"
                continue

            if first.upper() == "MODEL DETAILS":
                section = "model_details"
                continue

            if first == "" and len(row) >= 3 and row[1].upper() == "MEASUREMENTS":
                section = "summary_measurements"
                continue

            # Parse IV curve data
            if section == "iv_data":
                if len(row) >= 3:
                    voltage = parse_float(row[0])
                    current = parse_float(row[1])
                    power = parse_float(row[2])

                    if isinstance(voltage, float) and isinstance(current, float):
                        if not isinstance(power, float):
                            power = voltage * current

                        iv_rows.append(
                            {
                                "voltage_v": voltage,
                                "current_a": current,
                                "power_w": power,
                            }
                        )
                continue

            # Parse measured/model summary block
            if section == "summary_measurements":
                if len(row) >= 2:
                    key = clean_key(row[0])
                    measured_value = parse_float(row[1])
                    predicted_value = parse_float(row[2]) if len(row) >= 3 else None

                    if key:
                        metadata[f"measured_{key}"] = measured_value
                        metadata[f"model_predicted_{key}"] = predicted_value
                continue

            # Parse SolSensor block
            if section == "solsensor":
                if len(row) >= 2:
                    key = clean_key(row[0])
                    value = parse_float(row[1])

                    if key:
                        metadata[f"solsensor_{key}"] = value
                continue

            # Parse model details block
            if section == "model_details":
                if len(row) >= 2:
                    key = clean_key(row[0])
                    value = parse_float(row[1])

                    if key:
                        metadata[f"model_{key}"] = value

                    # Capture method if present
                    if len(row) >= 3 and row[2]:
                        metadata[f"model_{key}_method"] = row[2].replace("Method:", "").strip()
                continue

            # Parse top header block
            if section == "header":
                if len(row) >= 2:
                    key = clean_key(row[0])
                    value = parse_float(row[1])

                    if key:
                        metadata[key] = value

    # Useful derived fields
    metadata["number_iv_points"] = len(iv_rows)

    if iv_rows:
        metadata["parsed_min_voltage_v"] = min(r["voltage_v"] for r in iv_rows)
        metadata["parsed_max_voltage_v"] = max(r["voltage_v"] for r in iv_rows)
        metadata["parsed_min_current_a"] = min(r["current_a"] for r in iv_rows)
        metadata["parsed_max_current_a"] = max(r["current_a"] for r in iv_rows)
        metadata["parsed_max_power_w"] = max(r["power_w"] for r in iv_rows)
    else:
        metadata["parsed_min_voltage_v"] = None
        metadata["parsed_max_voltage_v"] = None
        metadata["parsed_min_current_a"] = None
        metadata["parsed_max_current_a"] = None
        metadata["parsed_max_power_w"] = None

    return metadata, iv_rows


def write_clean_iv_curve(iv_rows, output_path):
    """Write cleaned IV data to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["voltage_v", "current_a", "power_w"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(iv_rows)


def write_metadata_summary(metadata_rows, output_path):
    """Write one-row-per-file metadata summary."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_keys = []
    seen = set()

    for row in metadata_rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                all_keys.append(key)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(metadata_rows)


def process_all_files(raw_dir, processed_dir, metadata_out):
    raw_dir = Path(raw_dir)
    processed_dir = Path(processed_dir)
    metadata_out = Path(metadata_out)

    csv_files = sorted(raw_dir.rglob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in: {raw_dir}")
        return

    metadata_rows = []

    print(f"Found {len(csv_files)} CSV files.")
    print(f"Raw directory: {raw_dir}")
    print(f"Processed directory: {processed_dir}")
    print(f"Metadata output: {metadata_out}")
    print()

    for file_path in csv_files:
        try:
            metadata, iv_rows = parse_fluke_pva_csv(file_path, raw_dir)

            rel = file_path.relative_to(raw_dir)
            clean_name = safe_filename(file_path.stem) + "_clean_iv.csv"
            output_curve_path = processed_dir / rel.parent / clean_name

            write_clean_iv_curve(iv_rows, output_curve_path)

            metadata["clean_iv_output_file"] = str(output_curve_path)
            metadata_rows.append(metadata)

            print(f"Parsed: {rel}  |  IV points: {len(iv_rows)}")

        except Exception as e:
            print(f"ERROR parsing {file_path}: {e}")

    write_metadata_summary(metadata_rows, metadata_out)

    print()
    print("Done.")
    print(f"Metadata rows written: {len(metadata_rows)}")
    print(f"Metadata summary saved to: {metadata_out}")


# -----------------------------
# COMMAND LINE INTERFACE
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Parse Solmetric/Fluke PVA IV CSV files into clean IV curves and metadata summary."
    )

    parser.add_argument(
        "--raw-dir",
        default=str(DEFAULT_RAW_DIR),
        help="Folder containing raw IV CSV files.",
    )

    parser.add_argument(
        "--processed-dir",
        default=str(DEFAULT_PROCESSED_DIR),
        help="Folder where cleaned IV curve CSVs will be written.",
    )

    parser.add_argument(
        "--metadata-out",
        default=str(DEFAULT_METADATA_OUT),
        help="Output CSV file for one-row-per-IV-file metadata summary.",
    )

    args = parser.parse_args()

    process_all_files(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        metadata_out=args.metadata_out,
    )


if __name__ == "__main__":
    main()