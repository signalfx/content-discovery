# Dashboard Charts CSV Exporter

This Python script extracts chart details from a JSON export of dashboards and charts, and generates a CSV file based on the specified dashboard name.

---

## Features

- Accepts a JSON file export as input.
- Filters charts belonging to a specific dashboard (by dashboard name).
- Supports optional `--lab` flag to toggle which chart ID field (`chartId (lab)` vs `chartId`) is populated.
- Outputs a CSV file (`ChartDrill_{dashboard_name}.csv`) with a predefined header and values populated as per specification.

---

## Requirements

- Python 3.6 or above

---

## Usage

```bash
python CSVHelper.py --input <path_to_json_file> --dashboard-name "<dashboard_name> ...." [--lab]

## example 1
python CSVHelper.py --input ./group/Kubernetes.json --dashboard-name "K8s operations"

## example 2
python CSVHelper.py --input ./group/Kubernetes.json --dashboard-name "K8s operations" "Kubernetes Overview" --lab




## Arguments

    --input
    Path to the JSON file containing dashboard and chart exports.

    --dashboard-name
    The exact name of the dashboard to filter charts from.

    --lab (optional)
    If provided, populates the 'chartId (lab)' column in the CSV with chart IDs.
    If omitted, the 'chartId' column is populated instead.

