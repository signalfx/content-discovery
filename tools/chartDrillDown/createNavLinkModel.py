import csv
import json
import argparse
import requests

def fetch_chart_metadata(chart_id, token, debug=False):
    if not chart_id or chart_id.strip() in ('', '-', 'null'):
        if debug:
            print(f"[DEBUG] Skipping empty chartId")
        return None

    url = f"https://o11ytest.lab0.signalfx.com/v2/chart/{chart_id.strip()}"
    headers = {'x-sf-token': token}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            if debug:
                print(f"[DEBUG] Fetched chart {chart_id}: {response.json()}")
            return response.json()  # or extract certain fields if needed
        else:
            print(f"[WARN] Failed to fetch chart {chart_id}: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        print(f"[ERROR] Request failed for chart {chart_id}: {e}")
        return None

def update_chart(chart_id, chart_body, token, debug=False):
    url = f"https://o11ytest.lab0.signalfx.com/v2/chart/{chart_id}"
    headers = {
        'x-sf-token': token,
        'Content-Type': 'application/json'
    }
    try:
        response = requests.put(url, headers=headers, data=json.dumps(chart_body), timeout=10)
        if response.status_code in (200, 204):
            if debug:
                print(f"[DEBUG] Successfully updated chart {chart_id}")
            return True
        else:
            print(f"[ERROR] Failed to update chart {chart_id}: {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        print(f"[ERROR] RequestException while updating chart {chart_id}: {e}")
        return False


def clean_string(value):
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'").lower()
    return None if cleaned in ('', '-', 'null') else value.strip().strip('"').strip("'")


def clean_boolean(value):
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'").lower()
    return cleaned == 'true'


def generate_data_model(row, use_lab=False):
    # Choose correct column for navigatorId
    navigator_id = row.get('navigatorId (lab)' if use_lab else 'navigatorId')

    # Convert orderBy to list
    order_by_val = clean_string(row.get('orderBy'))
    order_by_list = [item.strip() for item in order_by_val.split(',')] if order_by_val else None

    chart_link = {
        "navigatorId": clean_string(navigator_id),
        "navigatorCode": clean_string(row.get('navigatorCode')),
        "navigatorVisualizationType": clean_string(row.get('navigatorVisualizationType')),
        "navigatorViewType": clean_string(row.get('navigatorView')),
        "metricClassCode": clean_string(row.get('metricClassCode')),
        "label": clean_string(row.get('label')),
        "isDefault": clean_boolean(row.get('isDefault')),
        "colorBy": clean_string(row.get('colorBy')),
        "orderBy": order_by_list,
        "type": "NavigatorLink"
    }

    dest_dashboard_id = clean_string(row.get('destinationDashboardId'))
    if dest_dashboard_id:
        chart_link["destinationDashboardId"] = dest_dashboard_id

    # Remove None values
    chart_link = {k: v for k, v in chart_link.items() if v is not None}

    data_model = {
        "chartLinks": [chart_link]
    }

    return json.dumps(data_model, indent=4)





def process_csv(input_file, output_file, debug=False, use_lab=False, token='', update_flag=False):
    with open(input_file, newline='', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        rows = list(reader)

        if debug:
            print(f"[DEBUG] Read {len(rows)} rows from {input_file}")
            for i, row in enumerate(rows):
                print(f"[DEBUG] Row {i + 1}: {row}\n")

        rows = [row for row in rows if any(field.strip() for field in row.values())]

        with open(output_file, 'w', encoding='utf-8') as outfile:


            for row in rows:
                row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}

                # Fetch chart metadata using chartId (if present)
                chart_id = row.get('chartId (lab)' if use_lab else 'chartId')
                chart_metadata = fetch_chart_metadata(chart_id, token, debug=debug)

                if debug:
                    if chart_id:
                        print(f"[DEBUG] chartId: {chart_id}")
                    if chart_metadata:
                        print(f"[DEBUG] Chart Metadata:\n{json.dumps(chart_metadata, indent=2)}\n")

                # Generate data model JSON string (you can also pass chart_metadata into this if needed)
                data_model_str = generate_data_model(row, use_lab=use_lab)

                if debug:
                    print(f"[DEBUG] Generated Data Model:\n{data_model_str}\n")

                outfile.write(data_model_str + '\n')


def process_csv(input_file, output_file, debug=False, use_lab=False, token='', update_flag=False):

    with open(input_file, newline='', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8') as outfile:

        reader = csv.DictReader(infile)
        rows = list(reader)

        if debug:
            print(f"[DEBUG] Loaded {len(rows)} rows from {input_file}")

        # Filter out empty rows if needed
        rows = [row for row in rows if any(field.strip() for field in row.values())]

        for row in rows:
            # Clean whitespace in all values
            row = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}

            # Select correct chartId column depending on --lab flag
            chart_id_col = 'chartId (lab)' if use_lab else 'chartId'
            chart_id = row.get(chart_id_col)

            if not chart_id:
                if debug:
                    print(f"[DEBUG] Missing chartId in row, skipping")
                continue

            # Fetch existing chart metadata via GET
            chart_metadata = fetch_chart_metadata(chart_id, token, debug=debug)
            if not chart_metadata:
                if debug:
                    print(f"[DEBUG] Could not fetch metadata for chartId {chart_id}, skipping row")
                continue

            # Generate chartLinks data model JSON string
            data_model_str = generate_data_model(row, use_lab=use_lab)

            # Parse JSON string back to dict for merging
            data_model = json.loads(data_model_str)

            # Replace or insert 'chartLinks' key in fetched chart metadata
            chart_metadata['chartLinks'] = data_model.get('chartLinks', [])

            # Write the combined JSON (pretty formatted) to output file
            outfile.write(json.dumps(chart_metadata, indent=4))
            outfile.write('\n\n')  # double newline for readability

            if debug:
                print(f"[DEBUG] Processed chartId {chart_id} - combined chart saved to output file.")

            # If --update flag is provided, PUT updated chart metadata back to API
            if update_flag:
                success = update_chart(chart_id, chart_metadata, token, debug=debug)
                if not success:
                    print(f"[WARN] Update failed for chartId {chart_id}")




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate chart drilldown data models from input CSV.")
    parser.add_argument('input_csv', help="Path to the input CSV file")
    parser.add_argument('--output_csv', default='output.csv', help="Path to the output CSV file (default: output.csv)")
    parser.add_argument('--debug', action='store_true', help="Enable debug output")
    parser.add_argument('--lab', action='store_true', help="Use 'navigatorId (lab)' from input CSV instead of 'navigatorId'")
    parser.add_argument('--token', required=True, help="SignalFx API token for chart lookup")
    parser.add_argument('--update', action='store_true', help='Send PUT request to update chart on SignalFx')


    args = parser.parse_args()

    process_csv(args.input_csv, args.output_csv, debug=args.debug, use_lab=args.lab, token=args.token, update_flag=args.update)
