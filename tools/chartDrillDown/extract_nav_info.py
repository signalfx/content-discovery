import json
import argparse
import os
import re
import csv

def extract_navigator_info(navigator_export):
    navigator = navigator_export.get("navigator", {})

    display_name = navigator.get("name", "unknown")
    navigator_code = navigator.get("uiModel", {}).get("id", "")
    navigator_id = navigator.get("id", "")

    metric_classes = navigator.get("metricClasses", [])

    result = []
    for mc in metric_classes:
        if not isinstance(mc, dict):
            continue

        code = mc.get("metricClassCode")
        columns = mc.get("metricClassColumns", [])

        if code:
            result.append({
                "Navigator name": display_name,
                "navigatorCode": navigator_code,
                "navigatorId": navigator_id,
                "metricClassCode": code,
                "orderBy": ", ".join(columns)  # <- renamed here
            })

    return result

def safe_dirname(path):
    base = os.path.basename(os.path.normpath(path))
    return base if base and re.search(r'\w', base) else "nav_info"

def process_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load {filepath}: {e}")
        return []

    if isinstance(data, dict):
        navigator_exports = [data.get("navigatorExport")] if "navigatorExport" in data else []
    elif isinstance(data, list):
        navigator_exports = [item.get("navigatorExport") for item in data if "navigatorExport" in item]
    else:
        print(f"Skipping {filepath}: not a list or dict")
        return []

    # Flatten results from extract_navigator_info
    results = []
    for nav in navigator_exports:
        if nav:
            results.extend(extract_navigator_info(nav))  # Use extend here
    return results


def main():
    parser = argparse.ArgumentParser(description="Extract and merge navigator metadata from JSON files in a directory")
    parser.add_argument("--input-dir", required=True, help="Directory containing JSON files")
    args = parser.parse_args()

    input_dir = args.input_dir
    json_files = [
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.endswith(".json") and os.path.isfile(os.path.join(input_dir, f))
    ]

    if not json_files:
        print("No JSON files found in directory.")
        return

    merged_data = []
    for filepath in json_files:
        merged_data.extend(process_json_file(filepath))

    if not merged_data:
        print("No valid navigatorExport data found.")
        return

    output_filename = f"{safe_dirname(input_dir)}.csv"
    fieldnames = [
        "Navigator name",
        "navigatorCode",
        "navigatorId",
        "metricClassCode",
        "orderBy"
    ]



    with open(output_filename, "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in merged_data:
            writer.writerow(row)

    print(f"Merged output written to: {output_filename}")

if __name__ == "__main__":
    main()
