# Chart Metadata Processor

This script processes a CSV file containing chart information, fetches metadata from SignalFx's API, generates a `chartLinks` data model, and optionally updates existing charts.

## 📋 Features

- Parses and cleans data from a CSV file.
- Fetches existing chart metadata from SignalFx.
- Generates and merges chart links as a new data model.
- Optionally updates charts in-place via PUT request.
- Supports a lab-specific mode for alternate column handling.
- Provides verbose debugging output if enabled.

---

## 🚀 Usage

```bash
python chart_processor.py input.csv --token <SIGNALFX_API_TOKEN> [--output_csv output.json] [--lab] [--debug] [--update]

|---------------------------------------------------------------------------------------------|
| Argument       | Description                                                                |
| -------------- | -------------------------------------------------------------------------- |
| `input.csv`    | Path to the input CSV file with chart data.                                |
| `--token`      | **(Required)** SignalFx API token.                                         |
| `--output_csv` | Output file path for processed chart data (default: `output.csv`).         |
| `--lab`        | Use alternate columns like `chartId (lab)` and `navigatorId (lab)`.        |
| `--debug`      | Print detailed debug output to the console.                                |
| `--update`     | If provided, the script will attempt to update the chart via PUT requests. |
|---------------------------------------------------------------------------------------------|


Dependencies

Install the required Python libraries:
|---------------------------------------------------------------------------------------------|
| pip install requests                                                                        |
|---------------------------------------------------------------------------------------------|


🛠 Example
|---------------------------------------------------------------------------------------------|
| python chart_processor.py charts.csv --token your-api-token-here --debug --update --lab     |
|---------------------------------------------------------------------------------------------|

