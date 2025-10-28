"""
This script converts data exported from Jeedom statistics into a format suitable for importing as a counter in Home Assistant. 
It processes the data by adding a prefix, formatting the date, and adjusting the data to include only full-hour timestamps.
The script performs the following steps:
1. Reads the input file and adds a specified prefix to each line.
2. Formats the date from the format "YYYY-MM-DD HH:MM:SS" to "DD.MM.YYYY HH:MM".
3. Replaces commas in numeric values with dots for consistency.
4. Adjusts the data to include only full-hour timestamps by interpolating values for non-full-hour timestamps based on the nearest previous full-hour data point.
5. Outputs the processed data to a new file in the required format with a header line: "statistic_id;start;state;sum".
Functions:
- add_prefix_and_format_date(input_file, temp_file, prefix): 
    Adds a prefix to each line, formats the date, and replaces commas in numeric values with dots.
- interpolate_value(prev_time, prev_value, current_time, current_value, target_time): 
    Linearly interpolates a value for a target time based on the previous full-hour data point.
- adjust_to_full_hours(temp_file, output_file): 
    Adjusts the data to include only full-hour timestamps by interpolating values for non-full-hour timestamps.
Usage:
Run the script with the following command:
        python3 process_file.py <input_file> <output_file> <prefix>
Arguments:
- <input_file>: Path to the input CSV file exported from Jeedom.
- <output_file>: Path to the output CSV file formatted for Home Assistant.
- <prefix>: A prefix to add to each line in the output file.
The script creates a temporary file during processing, which is deleted after the script completes.
"""
import csv
from datetime import datetime, timedelta
import sys

def add_prefix_and_format_date(input_file, temp_file, prefix):
    """Add a prefix to each line and format the date."""
    with open(input_file, "r", encoding="utf-8") as infile, open(temp_file, "w", encoding="utf-8", newline="") as outfile:
        reader = csv.reader(infile, delimiter=";")
        writer = csv.writer(outfile, delimiter=";")
        
        for row in reader:
            if len(row) > 1:
                # Add prefix and format the date
                old_date = row[0]
                new_date = datetime.strptime(old_date, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
                writer.writerow([prefix, new_date, row[1].replace(",", ".")])

def interpolate_value(prev_time, prev_value, current_time, current_value, target_time):
    """Linearly interpolate the value for the target time based on the previous full hour."""
    total_seconds = (current_time - prev_time).total_seconds()
    elapsed_seconds = (target_time - prev_time).total_seconds()
    value_diff = current_value - prev_value
    interpolated_value = prev_value + (value_diff * (elapsed_seconds / total_seconds))
    return round(interpolated_value, 2)  # Round to 2 decimal places for consistency

def adjust_to_full_hours(temp_file, output_file):
    """Adjust the data to only include full hours."""
    data = []

    # Read the temporary file
    with open(temp_file, "r", encoding="utf-8") as infile:
        reader = csv.reader(infile, delimiter=";")
        for row in reader:
            if len(row) >= 3:
                timestamp = datetime.strptime(row[1], "%d.%m.%Y %H:%M")
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
            if prev_time:
                interpolated_value = interpolate_value(prev_time, prev_value, current_time, current_value, current_time.replace(minute=0))
                adjusted_data.append((current_time.replace(minute=0), sensor_name, interpolated_value))

    # Write the adjusted data to the output file
    with open(output_file, "w", encoding="utf-8", newline="") as outfile:
        writer = csv.writer(outfile, delimiter=";")

        # Write the header line
        writer.writerow(["statistic_id", "start", "state", "sum"])
    
        for row in adjusted_data:
            writer.writerow([
                row[1],  # statistic_id
                row[0].strftime("%d.%m.%Y %H:%M"),  # start
                str(row[2]).replace(".", ","),  # state
                str(row[2]).replace(".", ",")   # sum (same as state)
            ])

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 process_file.py <input_file> <output_file> <prefix>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    prefix = sys.argv[3]
    temp_file = "temp_file.csv"  # Temporary file for intermediate processing

    # Step 1: Add prefix and format the date
    add_prefix_and_format_date(input_file, temp_file, prefix)

    # Step 2: Adjust to full hours
    adjust_to_full_hours(temp_file, output_file)

    # Clean up temporary file
    import os
    os.remove(temp_file)