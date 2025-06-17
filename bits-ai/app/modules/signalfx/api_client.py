import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("SIGNALFX_BASE_URL")
ORG_ID = os.getenv("SIGNALFX_ORG_ID")
API_TOKEN = os.getenv("SIGNALFX_API_TOKEN")

HEADERS = {
    "X-SF-TOKEN": API_TOKEN,
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json",
    "X-SF-SOURCE": "signalview"
}

def create_dashboard_group(name, description):
    url = f"{BASE_URL}/v2/dashboardgroup?organizationId={ORG_ID}"
    payload = {
        "name": name,
        "description": description,
        "permissions": {
            "acl": [
                {
                    "principalId": ORG_ID,
                    "principalType": "ORG",
                    "actions": ["READ", "WRITE"]
                }
            ],
            "parent": None
        }
    }
    print(url)
    print(payload)
    response = requests.post(url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        print("❌ Failed to create dashboard group:", response.text)
        return None
    
def get_dashboard(dashboard_id):
    url = f"{BASE_URL}/v2/dashboard/{dashboard_id}?organizationId={ORG_ID}"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        return response.json()
    else:
        print("❌ Failed to fetch dashboard:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return None

def create_chart(chart_json):
    url = f"{BASE_URL}/v2/chart?organizationId={ORG_ID}"
    response = requests.post(url, headers=HEADERS, json=chart_json)
    
    if response.status_code == 200:
        return response.json()
    else:
        print("❌ Failed to create chart:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
def add_chart_to_dashboard(dashboard, new_chart_entry):
    url = f"{BASE_URL}/v2/dashboard/{dashboard.get("id")}?organizationId={ORG_ID}"

    dashboard["charts"] = dashboard.get("charts", []) + [new_chart_entry]

    response = requests.put(url, headers=HEADERS, json=dashboard)

    if response.status_code == 200:
        print("✅ Adding chart to dashboard")
        return response.json()
    else:
        print("❌ Failed to add chart to dashboard:")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return None

def add_chart_list_to_dashboard(dashboard_id, chart_list):
    # Fetch current dashboard to get existing charts
    dashboard_data = get_dashboard(dashboard_id)
    if not dashboard_data:
        print(f"❌ Failed to get dashboard details to add charts")
        exit()

    row = 0
    column = 0
    
    for idx, chart_json in enumerate(chart_list):
        
        # 1. Create chart
        created_chart = create_chart(chart_json)
        if not created_chart:
            continue

        new_chart_id = created_chart.get("id")
        print(f"✅ Created chart: {created_chart.get('name')} (ID: {new_chart_id})")
        
        new_chart_entry = {
            "chartId": new_chart_id,
            "column": column,
            "row": row,
            "height": 1,
            "width": 6
        }
        
        # 2. Add chart to dashboard
        updated_dashboard = add_chart_to_dashboard(dashboard_data, new_chart_entry)
        if updated_dashboard:
            print(f"📌 Chart {created_chart.get('name')} (ID: {new_chart_id} added to dashboard\n")
    
        # 3. Update position for next chart
        column += 6
        if column >= 12:
            column = 0
            row += 1