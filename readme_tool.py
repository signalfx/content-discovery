import json
import os
from xlsxwriter import Workbook

def collect_nav_files():
    dest_list = []
    for dir, _, files in os.walk("navigators/"):
        for filename in files:
            if filename.endswith('.json'):
                dest_list.append(os.path.abspath(os.path.join(dir, filename)))
    print(dest_list)
    return dest_list


def prepare_import_qualifiers(nav_import_qualifiers):
    """
    Format
    [metric name] ([propertyName] [propertyOperation = or !=] propertyValue|propertyValue|propertyValue);
    [metric name] (propertyName [propertyOperation] propertyValue);
    """
    str_import_qualifiers = ""
    # To get the importQualifier
    for import_qualifier in nav_import_qualifiers:
        str_import_qualifiers += import_qualifier['metric'] + " "

        # To get the filters
        for value_property in import_qualifier.get('filters'):
            str_import_qualifiers += "(" + value_property.get('property') + " "
            prop_operation = "!=" if value_property["not"] else "="
            str_import_qualifiers += prop_operation + " "

            # To get the list of values appended with | (pipe)
            list_values = ""
            for prop_value in value_property.get('values'):
                list_values = prop_value + "|"
            # To remove last pipe symbol
            list_values = list_values[:-1]
            str_import_qualifiers += list_values + ")"
        str_import_qualifiers += "; "
    print(str_import_qualifiers)
    return str_import_qualifiers
test = [ {
        "filters" : [ {
          "not" : False,
          "property" : "monitored_resource",
          "values" : [ "spanner_instance", "gce_instance" ]
        } ],
        "metric" : "instance/cpu/utilization"
      }, {
        "filters" : [ ],
        "metric" : "http/server/response_count"
      }, {
        "filters" : [ ],
        "metric" : "container/memory/bytes_used"
      }, {
        "filters" : [ ],
        "metric" : "network/received_bytes_count"
      }, {
        "filters" : [ ],
        "metric" : "subscription/num_undelivered_messages"
      }, {
        "filters" : [ ],
        "metric" : "topic/send_request_count"
      }, {
        "filters" : [ ],
        "metric" : "function/execution_count"
      }, {
        "filters" : [ ],
        "metric" : "cluster/cpu_load"
      } ]
# prepare_import_qualifiers(test)


def write_xlsx_file(nav_data_list):
    """

    """
    ordered_list=["Name", "importQualifiers", "Category Group DisplayName", "Category DisplayName"] # List object calls by index, but the dict object calls items randomly

    wb = Workbook("OOTB Navigators.xlsx")
    ws = wb.add_worksheet("Navigators") # Or leave it blank. The default name is "Sheet 1"

    first_row=0
    for header in ordered_list:
        col=ordered_list.index(header) # We are keeping order.
        ws.write(first_row,col,header) # We have written first row which is the header of worksheet also.

    row=1
    for nav_data in nav_data_list:
        for _key,_value in nav_data.items():
            col=ordered_list.index(_key)
            ws.write(row,col,_value)
        row+=1 #enter the next row
    wb.close()

def collect_nav_name_desc_and_type(dest_list):
    """

    """
    nav_collections = []
    for dest_path in dest_list:
        print("---------")
        print(dest_path)
        with open(dest_path, 'r') as nav_file:
            data = json.load(nav_file)
            nav_collections.append({
                # 'name': data['navigatorExport']['navigator]['name'],
                'Name': data['navigatorExport']['navigator']['uiModel']['displayName'],
                # 'Is available for Customer?': data['navigatorExport']['navigator']['uiModel']['unreleased'],
                'importQualifiers': prepare_import_qualifiers(data['navigatorExport']['navigator']['importQualifiers']),
                'Category DisplayName': data['navigatorExport']['navigator'].get('navigatorCategoryDisplayName', ''),
                'Category Group DisplayName': data['navigatorExport']['navigator'].get('navigatorCategoryGroupDisplayName', '')
            })
    return nav_collections


def write_readmemd_file():
    """

    """
    nav_files = collect_nav_files()
    nav_list = collect_nav_name_desc_and_type(nav_files)
    write_xlsx_file(nav_list)

    # with open("test_readme2.md", 'w') as readme:
    #     readme.write("## Navigators\n")
    #     readme.write("| Name | Is available for Customer? | importQualifiers | Category Group DisplayName | Category DisplayName\n")
    #     readme.write("| ------- | --- | ------ | --- | --- |\n")
    #     cc = 0
    #     for nav in nav_list:
    #         cc +=1
    #         if cc>10:
    #             break
    #         is_available = "No" if nav.get('unreleased') else "Yes"
    #         nav_name = nav.get('name')
    #         imq = nav.get('importQualifiers')
    #         category  = nav.get('category')
    #         category_group = nav.get('category_group')
    #         readme.write(f"| {nav_name} | {is_available} | {imq} | {category} | {category_group} |\n")


write_readmemd_file()

