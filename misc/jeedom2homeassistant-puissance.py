"""
This script converts data exported from Jeedom statistics into a format suitable for importing as a counter in Home Assistant. 
It processes the data by formatting the date and adjusting the data to include only full-hour timestamps.
The script performs the following steps:
1. Reads the input file and formats the date from "YYYY-MM-DD HH:MM:SS" to "DD.MM.YYYY HH:MM".
2. Adjusts the data to include only full-hour timestamps by merging values for the same hour.
3. Outputs the processed data to a new file in the required format with a header line: "statistic_id;start;mean;min;max".
"""

import csv
from datetime import datetime
import sys

def process_file(input_file, output_file, prefix):
    """Process the input file and write the adjusted data to the output file."""
    data = {}

    # Read and process the input file
    with open(input_file, "r", encoding="utf-8") as infile:
        reader = csv.reader(infile, delimiter=";")
        for row in reader:
            if len(row) > 1:
                try:
                    # Parse and format the date
                    timestamp = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
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
    merged_data = {
        hour: {
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values)
        }
        for hour, values in data.items()
    }

    # Write the adjusted data to the output file
    with open(output_file, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile, delimiter=";")

        # Write the header line
        writer.writerow(["statistic_id", "start", "mean", "min", "max"])
        
        for hour, stats in sorted(merged_data.items()):
            writer.writerow([
                prefix,
                hour.strftime("%d.%m.%Y %H:%M"),
                f"{stats['mean']:.2f}".replace(".", ","),
                f"{stats['min']:.2f}".replace(".", ","),
                f"{stats['max']:.2f}".replace(".", ",")
            ])

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 jeedom2homeassistant-puissance.py <input_file> <output_file> <prefix>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    prefix = sys.argv[3]

    # Process the file
    process_file(input_file, output_file, prefix)