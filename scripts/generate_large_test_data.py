#!/usr/bin/env python3
"""
Generate large test data files for performance testing.

This script creates CSV files with ~100,000 rows using entities from config/configuration.yaml.
It generates both sensor data (mean/min/max) and counter data (sum/state).
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_sensor_data(output_file: Path, num_rows: int = 100000):
    """
    Generate sensor data with mean, min, max values.

    Uses temperature and humidity sensors from configuration.yaml.
    """
    print(f"Generating sensor data: {num_rows} rows...")

    # Sensor entities from config/configuration.yaml
    sensors = [
        {
            "id": "sensor.esp32_bathroom_bathroomtempsensor",
            "unit": "°C",
            "base_value": 22.0,
            "variation": 3.0,
        },
        {
            "id": "sensor.esp32_soundroom_soundroomtempsensor",
            "unit": "°C",
            "base_value": 21.0,
            "variation": 2.5,
        },
        {
            "id": "sensor.sens_all_changed",
            "unit": "C",
            "base_value": 20.0,
            "variation": 5.0,
        },
        {
            "id": "sensor.sens_part_overlap_new",
            "unit": "%",
            "base_value": 45.0,
            "variation": 15.0,
        },
        {
            "id": "sensor.sens_some_changed",
            "unit": "C",
            "base_value": 5.0,
            "variation": 10.0,
        },
        {
            "id": "sensor.sens_all_changed_new",
            "unit": "hPa",
            "base_value": 1013.0,
            "variation": 20.0,
        },
    ]

    # Start from 4 years ago, hourly data (must be full hours - minutes=0)
    # With ~16,666 rows per sensor at hourly intervals, this is ~694 days per sensor
    # Starting 4 years ago ensures all timestamps remain in the past
    start_date = datetime.now() - timedelta(days=1460)
    start_date = start_date.replace(minute=0, second=0, microsecond=0)

    rows = []
    rows_per_sensor = num_rows // len(sensors)

    for sensor in sensors:
        print(f"  Generating {rows_per_sensor} rows for {sensor['id']}...")

        for i in range(rows_per_sensor):
            timestamp = start_date + timedelta(hours=i)

            # Generate realistic mean/min/max values
            mean = sensor["base_value"] + random.uniform(-sensor["variation"], sensor["variation"])
            min_val = mean - random.uniform(0.5, 2.0)
            max_val = mean + random.uniform(0.5, 2.0)

            rows.append(
                {
                    "statistic_id": sensor["id"],
                    "start": timestamp.strftime("%d.%m.%Y %H:%M"),
                    "mean": f"{mean:.2f}",
                    "min": f"{min_val:.2f}",
                    "max": f"{max_val:.2f}",
                    "unit": sensor["unit"],
                }
            )

    # Write to CSV
    print(f"Writing {len(rows)} rows to {output_file}...")
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["statistic_id", "start", "mean", "min", "max", "unit"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Sensor data file created: {output_file} ({len(rows)} rows)")
    return len(rows)


def generate_counter_data(output_file: Path, num_rows: int = 100000):
    """
    Generate counter data with sum and state values.

    Uses energy and volume counters from configuration.yaml.
    """
    print(f"Generating counter data: {num_rows} rows...")

    # Counter entities from config/configuration.yaml
    counters = [
        {
            "id": "sensor.solaredge_i2_ac_energy_kwh",
            "unit": "kWh",
            "start_value": 43081.0,
            "hourly_increment": 0.5,  # ~0.5 kWh per hour average
        },
        {
            "id": "sensor.go_echarger_238557_wh",
            "unit": "kWh",
            "start_value": 8832.0,
            "hourly_increment": 0.3,  # ~0.3 kWh per hour average
        },
        {
            "id": "sensor.cnt_all_changed",
            "unit": "kWh",
            "start_value": 10.0,
            "hourly_increment": 0.1,
        },
        {
            "id": "sensor.cnt_part_overlap_new",
            "unit": "m3",
            "start_value": 100.0,
            "hourly_increment": 0.05,
        },
        {
            "id": "sensor.cnt_some_changed",
            "unit": "kWh",
            "start_value": 50.0,
            "hourly_increment": 0.2,
        },
        {
            "id": "sensor.cnt_all_changed_new",
            "unit": "L",
            "start_value": 200.0,
            "hourly_increment": 1.5,
        },
    ]

    # Start from 4 years ago, hourly data (must be full hours - minutes=0)
    # With ~16,666 rows per counter at hourly intervals, this is ~694 days per counter
    # Starting 4 years ago ensures all timestamps remain in the past
    start_date = datetime.now() - timedelta(days=1460)
    start_date = start_date.replace(minute=0, second=0, microsecond=0)

    rows = []
    rows_per_counter = num_rows // len(counters)

    for counter in counters:
        print(f"  Generating {rows_per_counter} rows for {counter['id']}...")

        current_sum = counter["start_value"]

        for i in range(rows_per_counter):
            timestamp = start_date + timedelta(hours=i)

            # Increment with some randomness
            increment = counter["hourly_increment"] * random.uniform(0.5, 1.5)
            current_sum += increment

            rows.append(
                {
                    "statistic_id": counter["id"],
                    "start": timestamp.strftime("%d.%m.%Y %H:%M"),
                    "sum": f"{current_sum:.2f}",
                    "state": f"{current_sum:.2f}",
                    "unit": counter["unit"],
                }
            )

    # Write to CSV
    print(f"Writing {len(rows)} rows to {output_file}...")
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["statistic_id", "start", "sum", "state", "unit"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Counter data file created: {output_file} ({len(rows)} rows)")
    return len(rows)


def generate_delta_data(output_file: Path, num_rows: int = 100000):
    """
    Generate delta data for counter imports.

    Delta values represent hourly changes in counter values.
    """
    print(f"Generating delta data: {num_rows} rows...")

    # Counter entities for delta import
    counters = [
        {
            "id": "sensor.solaredge_i2_ac_energy_kwh",
            "unit": "kWh",
            "hourly_delta": 0.5,  # ~0.5 kWh per hour average
        },
        {
            "id": "sensor.go_echarger_238557_wh",
            "unit": "kWh",
            "hourly_delta": 0.3,
        },
        {
            "id": "sensor.cnt_all_changed",
            "unit": "kWh",
            "hourly_delta": 0.1,
        },
    ]

    # Start from 4 years ago, hourly data (must be full hours - minutes=0)
    # With ~33,333 rows per counter at hourly intervals, this is ~1,388 days per counter
    # Starting 4 years ago ensures all timestamps remain in the past
    start_date = datetime.now() - timedelta(days=1460)
    start_date = start_date.replace(minute=0, second=0, microsecond=0)

    rows = []
    rows_per_counter = num_rows // len(counters)

    for counter in counters:
        print(f"  Generating {rows_per_counter} rows for {counter['id']}...")

        for i in range(rows_per_counter):
            timestamp = start_date + timedelta(hours=i)

            # Delta with some randomness (can be negative for solar at night)
            delta = counter["hourly_delta"] * random.uniform(0.0, 2.0)

            rows.append(
                {
                    "statistic_id": counter["id"],
                    "start": timestamp.strftime("%d.%m.%Y %H:%M"),
                    "delta": f"{delta:.3f}",
                    "unit": counter["unit"],
                }
            )

    # Write to CSV
    print(f"Writing {len(rows)} rows to {output_file}...")
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["statistic_id", "start", "delta", "unit"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Delta data file created: {output_file} ({len(rows)} rows)")
    return len(rows)


def generate_mixed_data(output_file: Path, num_rows: int = 100000):
    """
    Generate mixed data with both sensors and counters in one file.

    This tests the system's ability to handle multiple statistic types.
    """
    print(f"Generating mixed data: {num_rows} rows...")

    # Mix of sensors and counters
    entities = [
        # Sensors (mean/min/max)
        {
            "id": "sensor.esp32_bathroom_bathroomtempsensor",
            "unit": "°C",
            "type": "sensor",
            "base_value": 22.0,
            "variation": 3.0,
        },
        {
            "id": "sensor.sens_all_changed",
            "unit": "C",
            "type": "sensor",
            "base_value": 20.0,
            "variation": 5.0,
        },
        # Counters (sum/state)
        {
            "id": "sensor.solaredge_i2_ac_energy_kwh",
            "unit": "kWh",
            "type": "counter",
            "start_value": 43081.0,
            "hourly_increment": 0.5,
        },
        {
            "id": "sensor.cnt_all_changed",
            "unit": "kWh",
            "type": "counter",
            "start_value": 10.0,
            "hourly_increment": 0.1,
        },
    ]

    # Start from 4 years ago, hourly data (must be full hours - minutes=0)
    # With ~25,000 rows per entity at hourly intervals, this is ~1,041 days per entity
    # Starting 4 years ago ensures all timestamps remain in the past
    start_date = datetime.now() - timedelta(days=1460)
    start_date = start_date.replace(minute=0, second=0, microsecond=0)

    rows = []
    rows_per_entity = num_rows // len(entities)

    for entity in entities:
        print(f"  Generating {rows_per_entity} rows for {entity['id']} ({entity['type']})...")

        if entity["type"] == "sensor":
            for i in range(rows_per_entity):
                timestamp = start_date + timedelta(hours=i)
                mean = entity["base_value"] + random.uniform(-entity["variation"], entity["variation"])
                min_val = mean - random.uniform(0.5, 2.0)
                max_val = mean + random.uniform(0.5, 2.0)

                rows.append(
                    {
                        "statistic_id": entity["id"],
                        "start": timestamp.strftime("%d.%m.%Y %H:%M"),
                        "mean": f"{mean:.2f}",
                        "min": f"{min_val:.2f}",
                        "max": f"{max_val:.2f}",
                        "sum": "",
                        "state": "",
                        "unit": entity["unit"],
                    }
                )
        else:  # counter
            current_sum = entity["start_value"]
            for i in range(rows_per_entity):
                timestamp = start_date + timedelta(hours=i)
                increment = entity["hourly_increment"] * random.uniform(0.5, 1.5)
                current_sum += increment

                rows.append(
                    {
                        "statistic_id": entity["id"],
                        "start": timestamp.strftime("%d.%m.%Y %H:%M"),
                        "mean": "",
                        "min": "",
                        "max": "",
                        "sum": f"{current_sum:.2f}",
                        "state": f"{current_sum:.2f}",
                        "unit": entity["unit"],
                    }
                )

    # Write to CSV
    print(f"Writing {len(rows)} rows to {output_file}...")
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["statistic_id", "start", "mean", "min", "max", "sum", "state", "unit"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Mixed data file created: {output_file} ({len(rows)} rows)")
    return len(rows)


def main():
    """Generate all test data files."""
    print("=" * 80)
    print("Large Test Data Generator for Performance Testing")
    print("=" * 80)
    print()

    # Create output directory
    output_dir = Path("config/performance_test")
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")
    print()

    total_rows = 0

    # Generate sensor data (~100k rows)
    sensor_file = output_dir / "test_sensors_100k.csv"
    total_rows += generate_sensor_data(sensor_file, num_rows=100000)
    print()

    # Generate counter data (~100k rows)
    counter_file = output_dir / "test_counters_100k.csv"
    total_rows += generate_counter_data(counter_file, num_rows=100000)
    print()

    # Generate delta data (~100k rows)
    delta_file = output_dir / "test_delta_100k.csv"
    total_rows += generate_delta_data(delta_file, num_rows=100000)
    print()

    # Generate mixed data (~100k rows)
    mixed_file = output_dir / "test_mixed_100k.csv"
    total_rows += generate_mixed_data(mixed_file, num_rows=100000)
    print()

    print("=" * 80)
    print("✓ All test files generated successfully!")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Location: {output_dir}")
    print()
    print("Files created:")
    print(f"  1. {sensor_file.name} - Sensor data (mean/min/max)")
    print(f"  2. {counter_file.name} - Counter data (sum/state)")
    print(f"  3. {delta_file.name} - Delta data (for delta imports)")
    print(f"  4. {mixed_file.name} - Mixed sensors and counters")
    print()
    print("To test performance:")
    print("  1. Use Home Assistant UI to import these files")
    print("  2. Compare import times before/after optimization")
    print("  3. Monitor logs for timing information")
    print("=" * 80)


if __name__ == "__main__":
    main()
