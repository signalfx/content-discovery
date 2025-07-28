import json
import csv
import argparse
import sys
import re

def sanitize_filename(name):
    """Replace unsafe characters in filenames."""
    return re.sub(r'[^\w\-_\. ]', '_', name)

def export_dashboard_charts(dashboard_name, dashboard_data, chart_map, lab_flag):
    chart_ids = [c.get("chartId") for c in dashboard_data.get("charts", [])]

    output_filename = f"ChartDrill_{sanitize_filename(dashboard_name)}.csv"
    header = [
        "Dashboard Name", "Chart Name", "chartId (lab)", "chartId",
        "Navigator name", "navigatorId (lab)", "navigatorId", "navigatorCode",
        "navigatorVisualizationType", "metricClassCode", "colorBy", "orderBy",
        "navigatorView", "label", "isDefault", "destinationDashboardId", "Notes"
    ]

    with open(output_filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)

        for chart_id in chart_ids:
            chart = chart_map.get(chart_id)
            if not chart:
                continue

            chart_name = chart.get("name", "")
            chart_id_lab = chart_id if lab_flag else ""
            chart_id_std = "" if lab_flag else chart_id

            row = [
                dashboard_name,
                chart_name,
                chart_id_lab,
                chart_id_std,
                "", "", "", "", "", "", "", "", "", "", "", "", ""
            ]
            writer.writerow(row)

    print(f"CSV generation completed: {output_filename}")

def main():
    parser = argparse.ArgumentParser(description="Extract dashboard charts to CSV")
    parser.add_argument("--input", required=True, help="Input JSON file path")
    parser.add_argument(
        "--dashboard-name",
        required=True,
        nargs="+",
        help="One or more dashboard names to process (use quotes for names with spaces)"
    )
    parser.add_argument("--lab", action="store_true", help="Populate 'chartId (lab)' instead of 'chartId'")
    args = parser.parse_args()

    # Load JSON data
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    dashboards = data.get("dashboardExports", [])
    chart_exports = data.get("chartExports", [])

    # Build chart lookup map
    chart_map = {}
    for c_export in chart_exports:
        chart = c_export.get("chart", {})
        if "id" in chart:
            chart_map[chart["id"]] = chart

    # Lookup and export for each dashboard name
    found_any = False
    for name in args.dashboard_name:
        matched_dashboard = None
        for d in dashboards:
            if d.get("dashboard", {}).get("name") == name:
                matched_dashboard = d["dashboard"]
                break

        if matched_dashboard:
            found_any = True
            export_dashboard_charts(name, matched_dashboard, chart_map, args.lab)
        else:
            print(f"Invalid dashboard name: '{name}'")

    if not found_any:
        sys.exit(1)

if __name__ == "__main__":
    main()
