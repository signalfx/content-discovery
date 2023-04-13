import json
import os
import gspread

from oauth2client.service_account import ServiceAccountCredentials


def collect_json_files(path):
    dest_list = []
    if path == "navigators/":
        for dir, _, files in os.walk(path):
            for filename in files:
                if filename.endswith('.json'):
                    with open(os.path.abspath(os.path.join(dir, filename))) as file:
                        nav_json = json.load(file)
                        nav_json = nav_json['navigatorExport']['navigator']
                        keys = nav_json['uiModel'].keys()
                        # To ignore the navigators with architectural type, and navigators with no Name(not getting displayed) and navigators with name "Nodes", "Pods", and "Containers" (Because older version file is also present in the repo and we have to ignore those) and ignore navigators with sites = "signalview" and ignored navigators that are unreleased
                        if 'o11yProductName' in keys and (nav_json['navigatorType'] != 'architectural') \
                                and (nav_json['uiModel']['o11yProductName'] is not None and
                                     nav_json['uiModel']['o11yProductName'] != "Pods" and
                                     nav_json['uiModel']['o11yProductName'] != "Containers" and
                                     nav_json['uiModel']['o11yProductName'] != "Nodes") and (
                                nav_json['sites'] != "signalview") and (not nav_json['uiModel']['unreleased']):
                            dest_list.append(os.path.abspath(os.path.join(dir, filename)))

    elif path == "group/" or path == "detector/":
        for dir, _, files in os.walk(path):
            for filename in files:
                if filename.endswith('.json'):
                    dest_list.append(os.path.abspath(os.path.join(dir, filename)))
    return dest_list


def prepare_import_qualifiers(nav_import_qualifiers):
    """
    Format
    [metric name] ([propertyName] [propertyOperation = or !=] propertyValue|propertyValue|propertyValue);
    [metric name] (propertyName [propertyOperation] propertyValue);
    """
    # Handle or add "and" "or" words and add "*" if null in values

    str_import_qualifiers = ""
    dummy_import_qualifiers = ""
    # To get the importQualifier
    for import_qualifier in nav_import_qualifiers:
        str_import_qualifiers += import_qualifier['metric'] + " "

        # To get the filters
        for value_property in import_qualifier.get('filters'):
            if 'property' in value_property.keys():
                str_import_qualifiers += "(" + (
                    value_property.get('property') if value_property.get('property') != "" else "*")
                if str_import_qualifiers[-1] == '*':
                    str_import_qualifiers += ") & "
                    continue

                # Property operation {"not": false} will be considered as != and {"not": true} will be considered as =
                prop_operation = " != " if value_property["not"] else " = "
                str_import_qualifiers += prop_operation + " "

                # To get the list of values appended with | (pipe)
                list_values = ""
                for prop_value in value_property.get('values'):
                    list_values += prop_value + " | "
                # Check if the list_values is null, replace it with *
                if list_values == "":
                    list_values = "* | "
                # To remove last pipe symbol
                # Todo: It will always get remove as we have same level of indentation
                list_values = list_values[:-3]
                str_import_qualifiers += list_values + ")" + " & "
        if str_import_qualifiers == dummy_import_qualifiers + import_qualifier['metric'] + " ":
            str_import_qualifiers += "(*)"
        else:
            # To remove last & symbol
            str_import_qualifiers = str_import_qualifiers[:-3]
        str_import_qualifiers += ";  OR\n"
        dummy_import_qualifiers = str_import_qualifiers
    # To remove last line "  OR\n" in the string as it get appended at L-74
    str_import_qualifiers = str_import_qualifiers[:-5]
    return str_import_qualifiers


def sort_list(content_list):
    """
 
    """
    return sorted(content_list, key=lambda x: x[0].lower())


def write_xlsx_file(type, data_list):
    """

    """
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json')
    file = gspread.authorize(creds)
    workbook = file.open("O11y Out of the Box Inventory Test")

    if type == 'navigator':
        sheet = workbook.worksheet('Navigators')

        # Clearing the Cells
        sheet.batch_clear(["A2:D120"])

        # Sort the list alphabetically
        data_list = sort_list(data_list)

        # Writing into GSheet
        sheet.update('A2:D120', data_list)
    elif type == 'dashboard':
        sheet = workbook.worksheet('Dashboards')

        # Clearing the Cells
        sheet.batch_clear(["A2:B200"])

        # Sort the list alphabetically
        data_list = sort_list(data_list)

        # Writing into GSheet
        sheet.update('A2:B200', data_list)
    elif type == 'detector':
        sheet = workbook.worksheet('Detectors')

        # Clearing the Cells
        sheet.batch_clear(["A2:B100"])

        # Sort the list alphabetically
        data_list = sort_list(data_list)

        # Writing into GSheet
        sheet.update('A2:B100', data_list)


def collect_content_name_desc_and_type(dest_list):
    """

    """
    collections = []
    if 'content-discovery/navigators/' in dest_list[0]:
        for dest_path in dest_list:
            with open(dest_path, 'r') as nav_file:
                data = json.load(nav_file)
                nav_json = data['navigatorExport']['navigator']
                collections.append([
                    nav_json['uiModel']['o11yProductName'],
                    prepare_import_qualifiers(nav_json['importQualifiers']),
                    nav_json.get('navigatorCategory') if nav_json.get('navigatorCategory') is not None else "Others",
                    nav_json.get('navigatorCategoryGroupDisplayName') if nav_json.get(
                        'navigatorCategoryGroupDisplayName') is not None else "Others"
                ])
    elif 'content-discovery/group/' in dest_list[0]:
        for dest_path in dest_list:
            with open(dest_path, 'r') as db_file:
                data = json.load(db_file)
                collections.append([
                    data['groupExport']['group']['name'],
                    prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']),
                ])
    elif 'content-discovery/detector/' in dest_list[0]:
        for dest_path in dest_list:
            with open(dest_path, 'r') as db_file:
                data = json.load(db_file)
                collections.append([
                    data['detectorExport']['detector']['name'],
                    prepare_import_qualifiers(data['detectorExport']['detector']['importQualifiers']),
                ])
    return collections


def main():
    """

    """
    nav_files = collect_json_files("navigators/")
    nav_list = collect_content_name_desc_and_type(nav_files)
    write_xlsx_file("navigator", nav_list)

    db_files = collect_json_files("group/")
    db_list = collect_content_name_desc_and_type(db_files)
    write_xlsx_file("dashboard", db_list)

    dt_files = collect_json_files("detector/")
    dt_list = collect_content_name_desc_and_type(dt_files)
    write_xlsx_file("detector", dt_list)


if __name__ == "__main__":
    main()
