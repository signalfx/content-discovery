from app_utility import load_prompt, read_yaml_file, get_yaml_dump, extract_metrics_with_attributes
from ai_service import call_ollama, call_bridgeIt
from api_service import create_dashboard_group, add_chart_list_to_dashboard
import json
import os
from pprint import pformat
from dotenv import load_dotenv


load_dotenv()
BASE_URL = os.getenv("SIGNALFX_BASE_URL")

def generate_dashboard_group(service_type):
    prompt = load_prompt("./prompts/dashboard_group.txt", {"service_name": service_type})
    response = call_bridgeIt(prompt)
    metadata = json.loads(response)
    result = create_dashboard_group(metadata['name'], metadata['description'])

    if result:
        group_id = result.get("id")
        dashboards = result.get("dashboards", [])
        dashboard_configs = result.get("dashboardConfigs", [])

        if dashboards and dashboard_configs:
            dashboard_id = dashboards[0]
            config_id = dashboard_configs[0].get("configId")
            dashboard_url = f"{BASE_URL}/#/dashboard/{dashboard_id}?groupId={group_id}&configId={config_id}"
            print("✅ Dashboard Group Created:")
            print(f"📛 Name: {result['name']}")
            print(f"📛 Description: {result['description']}")
            print(f"🆔 Group ID: {group_id}")
            print(f"🔗 Dashboard URL: {dashboard_url}\n")
        else:
            print("⚠️ Dashboard group created but dashboard/config info not found in response.")

        return {
            "group_id": group_id,
            "dashboard_id": dashboard_id
        }
        
    else:
        print("❌ Dashboard group creation failed.")
        return None

def generate_chart_list(service_data):
    prompt = load_prompt("./prompts/chart_list.txt", {"service_data_dump": pformat(service_data)})
    response = call_bridgeIt(prompt)
    print(response)
    metadata = json.loads(response)
    return metadata

def generate_timeseries_charts(chart_list):
    timeseries_charts = []

    for chart in chart_list:
        if chart["type"] != "TimeSeriesChart":
            continue
        
        print(f"✅ Generating a {chart["type"]} with title {chart["title"]}:")
        
        prompt = load_prompt(
            "./prompts/chart_type_timeseries.txt",
            {
                "title": chart["title"],
                "description": chart["description"],
                "programText": chart["programText"]
            }
        )
        
        response = call_bridgeIt(prompt)
        
        try:
            chart_json = json.loads(response)
            timeseries_charts.append(chart_json)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON for chart: {chart['title']}")
            print(f"🔍 Raw response: {response}\n")

    return timeseries_charts

if __name__ == "__main__":
    servicefilename = "apache.yaml"
    service_yaml = read_yaml_file(servicefilename)
    extracted_data = extract_metrics_with_attributes(service_yaml)
    print(extracted_data)
    
    # existing_dashboard_id = "GnTwGWgAcAA"  # Use this if it's set

    # if existing_dashboard_id:
    #     print(f"🎯 Using existing dashboard ID: {existing_dashboard_id}")
    #     dashboard_id = existing_dashboard_id
    # else:
    #     print("🎨 Creating dashboard for apache")
    #     dashboard_group = generate_dashboard_group(service_yaml.get("type"))
    #     dashboard_id = dashboard_group.get("dashboard_id")
    
    # print("🧠 Thinking of what charts to generate")
    # chart_list = generate_chart_list(extract_metrics_with_attributes(service_yaml))
    # filtered = [item for item in chart_list if item.get("type") == "TimeSeriesChart"][:5]
    # timeseries_chart_list = generate_timeseries_charts(filtered)
    # add_chart_list_to_dashboard(dashboard_id, timeseries_chart_list)
    
    # servicefilename = "redis.yaml"
    # service_yaml = read_yaml_file(servicefilename)
    
    # print("🎨 Creating dashboard for redis")
    # dashboard_group = generate_dashboard_group(service_yaml.get("type"))
    # print("🧠 Thinking of what charts to generate")
    # chart_list = generate_chart_list(extract_metrics_with_attributes(service_yaml))
    # filtered = [item for item in chart_list if item.get("type") == "TimeSeriesChart"][:5]
    # timeseries_chart_list = generate_timeseries_charts(filtered)
    # add_chart_list_to_dashboard(dashboard_group.get("dashboard_id"), timeseries_chart_list)
    