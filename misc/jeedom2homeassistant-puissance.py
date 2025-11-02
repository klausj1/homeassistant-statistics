"""
Convert Jeedom-exported CSV to Home Assistant power statistics format.

The script reads an input CSV, formats the dates, and adjusts the data
so only full-hour timestamps remain. The output CSV contains the header
"statistic_id;start;mean;min;max".

Usage: python3 jeedom2homeassistant-puissance.py <input_file> <output_file> <prefix>
"""

import contextlib
import csv
import datetime
import sys
from pathlib import Path

MIN_ROW_COLS = 2
REQUIRED_ARGS = 4


def process_file(input_file: str, output_file: str, prefix: str) -> None:
    """
    Process the input file and write the adjusted data to the output file.

    Reads time-series data from input_file, groups by hour calculating
    statistics, and writes results to output_file using prefix in the id.
    """
    data: dict[datetime.datetime, list[float]] = {}

    # Read and process the input file
    infile_path = Path(input_file)
    with infile_path.open(encoding="utf-8") as infile:
        reader = csv.reader(infile, delimiter=";")
        for row in reader:
            if len(row) > MIN_ROW_COLS:
                try:
                    # Parse and format the date
                    timestamp = datetime.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.UTC)
                    value = float(row[1].replace(",", "."))
                    # Round down to the nearest full hour
                    full_hour = timestamp.replace(minute=0, second=0, microsecond=0)
                    if full_hour not in data:
                        data[full_hour] = []
                    data[full_hour].append(value)
                except ValueError:
                    # Skip invalid rows
                    continue

    # Merge values for each full hour (calculate mean, min, and max)
    merged_data = {hour: {"mean": sum(values) / len(values), "min": min(values), "max": max(values)} for hour, values in data.items()}

    # Write the adjusted data to the output file
    outfile_path = Path(output_file)
    with outfile_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile, delimiter=";")

        # Write the header line
        writer.writerow(["statistic_id", "start", "mean", "min", "max"])

        for hour, stats in sorted(merged_data.items()):
            writer.writerow(
                [
                    prefix,
                    hour.strftime("%d.%m.%Y %H:%M"),
                    f"{stats['mean']:.2f}".replace(".", ","),
                    f"{stats['min']:.2f}".replace(".", ","),
                    f"{stats['max']:.2f}".replace(".", ","),
                ]
            )


def _main() -> int:
    if len(sys.argv) != REQUIRED_ARGS:
        sys.stderr.write("Usage: python3 jeedom2homeassistant-puissance.py <input_file> <output_file> <prefix>\n")
        return 1

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    prefix = sys.argv[3]

    # Process the file
    process_file(input_file, output_file, prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
