import json
import yaml
from o11y_ootb_inventory import GitlabInventory

class OOTBDocAutomation:

    # Navigators in which dashboards are imported via dashboard query
    ASSOCIATED_DASHBOARDS_TO_NAVIGATORS = {'Cloud functions':{'aggregate': "GCF overview", 'instance': "GCF function"}, 'Compute engine':{'aggregate': "Compute engine instances", 'instance': "Compute engine instance"}, 'Azure functions':{'aggregate': "Azure function apps", 'instance': "Azure function app"}, 'Virtual machines':{'aggregate': "Azure virtual machines", 'instance': "Azure virtual machine"}, 'Lambda functions':{'aggregate': "Lambda (AWS) overview", 'instance': "Lambda (AWS) function"}, "DynamoDB": {'instance': "N/A"}}

    # Dashboards that are exported to navigators via dashboard query
    DASHBOARD_TYPE = {"Lambda (SignalFx) overview": "aggregated", "Lambda (SignalFx) function": "instance", "Lambda (AWS) overview": "aggregated", "Lambda (AWS) function": "instacne", "Compute engine instances": "aggregated", "Compute engine instance": "instance", "Compute engine instances (StackDriver)": "aggregated", "Compute engine instance (StackDriver)": "instance", "GCF (STACKDRIVER) FUNCTION": "instance", "GCF (STACKDRIVER) overview": "aggregated", "GCF (SIGNALFX) overview": "aggregated", "GCF (SIGNALFX) function": "instance", "(Azure) function app": "instance", "(Azure) function apps": "aggregated", "(SignalFx) azure function": "instance", "(SignalFx) azure functions": "aggregated", "Azure Virtual Machines": "aggregated", "Azure Virtual Machine": "instance", "Azure Virtual Machine (Azure monitor)": "instance", "Azure Virtual Machines (Azure monitor)": "aggregated"}

    @classmethod
    def get_dashbaord_mapping(cls, dashboard_paths, navigator_paths):
        """
        Helper method to map dashboard ids to it's dashboards name and view support(if exists) respectively.
        """

        dashboard_mapping = dict()

        # Helps to prepare dashboard mapping between dashboard id and it's name by traversing the dashboard groups.
        for dashboard_path in dashboard_paths:
            with open(dashboard_path, 'r') as file:
                data = json.load(file)
                if 'content-discovery/group' in dashboard_path:
                    
                    for dashboard in data["dashboardExports"]:
                        dashboard_mapping[dashboard['dashboard']['id']] = {"name": dashboard['dashboard']['name'], "view_support":list()}
        
        # Helps to add the appropriate view support(instance, aggreagated) for a dashboard by traversing through navigators.
        for navigator_path in navigator_paths:
            with open(navigator_path, 'r') as file:
                data = json.load(file)
                if 'content-discovery/navigators' in navigator_path:
                    nav_json = data['navigatorExport']['navigator']
                    if nav_json.get('aggregateDashboards'):
                        [dashboard_mapping[dashboard]["view_support"].append('aggregated') for dashboard in nav_json.get('aggregateDashboards')]
                    if nav_json.get('instanceDashboards'):
                        [dashboard_mapping[dashboard]["view_support"].append('instance') for dashboard in nav_json.get('instanceDashboards')]  
        return dashboard_mapping


    def collect_inventory_data(cls, dest_list, dashboard_mapping):
        """
        Helper method to get the OOTB's inventory data.
        """
        
        collections = dict()

        for dest_path in dest_list:
            with open(dest_path, 'r') as file:
                data = json.load(file)
                if 'content-discovery/navigators/' in dest_path:
                    nav_json = data['navigatorExport']['navigator']

                    # Collecting the associated dashboards(aggreagted, instacne) with the help of dashboard_mapping we created
                    collections[nav_json['uiModel']['o11yProductName']] = {

                        "category_display_name": nav_json.get('navigatorCategory') if nav_json.get(
                            'navigatorCategory') is not None else "Others",

                        "associated_dashboards": {
                            "aggregated": [ dashboard_mapping[dashboard]["name"] for dashboard in nav_json.get("aggregateDashboards") ] if nav_json.get("aggregateDashboards") is not None else cls.ASSOCIATED_DASHBOARDS_TO_NAVIGATORS[nav_json['uiModel']['o11yProductName']]["aggregate"], 
                            "instance": [ dashboard_mapping[dashboard]["name"] for dashboard in nav_json.get("instanceDashboards")  ] if nav_json.get("instanceDashboards") is not None else cls.ASSOCIATED_DASHBOARDS_TO_NAVIGATORS[nav_json['uiModel']['o11yProductName']]["instance"]
                            }
                    }

                elif 'content-discovery/group/' in dest_path:
                    group_name = data['groupExport']['group']['name']
                    group_dashboards_ids = data['groupExport']['group']['dashboards']
                    for id in group_dashboards_ids:
                        
                        # Collecting view_support of a particular dashboard with help of dashboard_mapping
                        collections[dashboard_mapping[id]["name"]] = {
                            "dashboard_group": group_name,
                            "view_support": dashboard_mapping[id]["view_support"][0] if dashboard_mapping[id]["view_support"] else (cls.DASHBOARD_TYPE[dashboard_mapping[id]["name"]] if dashboard_mapping[id]["name"] in cls.DASHBOARD_TYPE.keys() else "N/A")
                        }
                else:
                    break
        return collections
    
if __name__ == "__main__":
    collect_files = GitlabInventory()
    inventory = OOTBDocAutomation()

    # Helps to create mapping between dashboard id to it's name and view support(aggregated, instance)
    dashboard_mapping = inventory.get_dashbaord_mapping(collect_files.collect_json_files('group/'), collect_files.collect_json_files('navigators/'))

    # Create the navigator JSON with help of dashboard mapping
    collection_nav = inventory.collect_inventory_data(collect_files.collect_json_files('navigators/'), dashboard_mapping)

    # Create the dashboard JSON with help of dashboard mapping
    collection_dash = inventory.collect_inventory_data(collect_files.collect_json_files('group/'), dashboard_mapping)

    collection_nav = dict(sorted(collection_nav.items())) # Sort the navigator JSON on basis of navigator name
    collection_dash = dict(sorted(collection_dash.items())) # Sort the dashboard JSON on basis of dashboard name

    nav_collection = {"Navigators": collection_nav}
    dash_collection = {"Dashboards": collection_dash}

    # Create the YAML file for dashboards built-in content (OOTB)
    with open('dashboards_builtin_content.yaml', 'w') as yaml_file:
        yaml.dump(dash_collection, yaml_file, sort_keys=False)

    # Create the YAML file for navigators built-in content (OOTB)
    with open('navigators_builtin_content.yaml', 'w') as yaml_file:
        yaml.dump(nav_collection, yaml_file, sort_keys=False)


