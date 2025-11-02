"""
Convert Jeedom-exported CSV to Home Assistant counter format.

The script reads an input CSV, adds a prefix to sensor ids, reformats
dates and adjusts the data so only full-hour timestamps remain
(interpolating where necessary). The output CSV contains the header
"statistic_id;start;state;sum".

Usage: python3 process_file.py <input_file> <output_file> <prefix>
"""

import contextlib
import csv
import datetime
import sys
from pathlib import Path

# typing imports intentionally omitted; use built-in generics (list/tuple) for annotations

MIN_ROW_COLS = 3


def add_prefix_and_format_date(input_file: str, temp_file: str, prefix: str) -> None:
    """
    Add a prefix to each line and format the date.

    Writes intermediate results to ``temp_file``.
    """
    infile_path = Path(input_file)
    outfile_path = Path(temp_file)

    with infile_path.open(encoding="utf-8") as infile, outfile_path.open("w", encoding="utf-8", newline="") as outfile:
        reader = csv.reader(infile, delimiter=";")
        writer = csv.writer(outfile, delimiter=";")

        for row in reader:
            if len(row) > 1:
                old_date = row[0]
                # parse as UTC-aware datetime
                new_date = datetime.datetime.strptime(old_date, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.UTC).strftime("%d.%m.%Y %H:%M")
                writer.writerow([prefix, new_date, row[1].replace(",", ".")])


def interpolate_value(
    prev_time: datetime.datetime,
    prev_value: float,
    current_time: datetime.datetime,
    current_value: float,
    target_time: datetime.datetime,
) -> float:
    """
    Linearly interpolate the value for the target time.

    Returns a float rounded to 2 decimals. If the interval is zero
    seconds, returns the previous value.
    """
    total_seconds = (current_time - prev_time).total_seconds()
    if total_seconds == 0:
        return round(prev_value, 2)

    elapsed_seconds = (target_time - prev_time).total_seconds()
    value_diff = current_value - prev_value
    interpolated_value = prev_value + (value_diff * (elapsed_seconds / total_seconds))
    return round(interpolated_value, 2)


def adjust_to_full_hours(temp_file: str, output_file: str) -> None:
    """Adjust the data to only include full hours."""
    data: list[tuple[datetime.datetime, str, float]] = []

    # Read the temporary file
    infile_path = Path(temp_file)
    with infile_path.open(encoding="utf-8") as infile:
        reader = csv.reader(infile, delimiter=";")
        for row in reader:
            if len(row) >= MIN_ROW_COLS:
                timestamp = datetime.datetime.strptime(row[1], "%d.%m.%Y %H:%M").replace(tzinfo=datetime.UTC)
                value = float(row[2])
                data.append((timestamp, row[0], value))

    # Sort data by timestamp
    data.sort(key=lambda x: x[0])

    # Adjust to full hours
    adjusted_data = []
    for i in range(len(data)):
        current_time, sensor_name, current_value = data[i]

        # If the current time is already a full hour, keep it
        if current_time.minute == 0:
            adjusted_data.append((current_time, sensor_name, current_value))
        else:
            # Find the previous full-hour data point
            prev_time, prev_value = None, None

            for j in range(i - 1, -1, -1):
                if data[j][0].minute == 0:
                    prev_time, prev_value = data[j][0], data[j][2]
                    break

            # Interpolate the value if a previous full-hour point exists
            if prev_time is not None and prev_value is not None:
                interpolated_value = interpolate_value(prev_time, prev_value, current_time, current_value, current_time.replace(minute=0))
                adjusted_data.append((current_time.replace(minute=0), sensor_name, interpolated_value))

    # Write the adjusted data to the output file
    outfile_path = Path(output_file)
    with outfile_path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile, delimiter=";")

        # Write the header line
        writer.writerow(["statistic_id", "start", "state", "sum"])

        for row in adjusted_data:
            writer.writerow(
                [
                    row[1],  # statistic_id
                    row[0].strftime("%d.%m.%Y %H:%M"),  # start
                    str(row[2]).replace(".", ","),  # state
                    str(row[2]).replace(".", ","),  # sum (same as state)
                ]
            )


REQUIRED_ARGS = 4


def _main() -> int:
    if len(sys.argv) != REQUIRED_ARGS:
        sys.stderr.write("Usage: python3 process_file.py <input_file> <output_file> <prefix>\n")
        return 1

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    prefix = sys.argv[3]
    temp_file = "temp_file.csv"  # Temporary file for intermediate processing

    # Step 1: Add prefix and format the date
    add_prefix_and_format_date(input_file, temp_file, prefix)

    # Step 2: Adjust to full hours
    adjust_to_full_hours(temp_file, output_file)

    # Clean up temporary file
    with contextlib.suppress(FileNotFoundError):
        Path(temp_file).unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
