import json
import os
import gspread
import argparse
import base64

from oauth2client.service_account import ServiceAccountCredentials

NAVIGATOR_EXCLUDE_LIST = ['Pods','Containers','Nodes']

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
                                and nav_json['uiModel']['o11yProductName'] is not None \
                                and nav_json['uiModel']['o11yProductName'] not in NAVIGATOR_EXCLUDE_LIST and ( \
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
            #Checking if 'property' property exist in filters block, if not '(*)' will be added in L-77
            if 'property' in value_property.keys():
                #Adding property value if exist, else '*' (asterisk)
                str_import_qualifiers += "(" + (
                    value_property.get('property') if value_property.get('property') != "" else "*")
                #If no property value exist, ending the current iteration with ') &'
                if str_import_qualifiers[-1] == '*':
                    str_import_qualifiers += ") & "
                    continue
                # Property operation {"not": false} will be considered as = and {"not": true} will be considered as !=
                prop_operation = " != " if value_property["not"] else " = "
                str_import_qualifiers += prop_operation + " "

                # To get the list of values appended with | (pipe)
                list_values = ""
                for prop_value in value_property.get('values'):
                    list_values += prop_value + " | "
                # Check if the list_values is null, replace it with *
                if list_values == "":
                    list_values = "*"
                # Check if the list_value is not null, remove the extra '|' (pipe)
                else:
                    list_values = list_values[:-3]
                # Adding ') &' at last, '&' will be removed in L-81
                str_import_qualifiers += list_values + ") & "
        
        #If 'property' property doesn't exist
        if str_import_qualifiers == dummy_import_qualifiers + import_qualifier['metric'] + " ":
            str_import_qualifiers += "(*)"
        else:
            # To remove last '&' symbol with one or multiple filter values
            str_import_qualifiers = str_import_qualifiers[:-3]
        str_import_qualifiers += ";  OR\n"
        dummy_import_qualifiers = str_import_qualifiers
    # To remove last line "  OR\n" in the string as it get appended at L-82
    str_import_qualifiers = str_import_qualifiers[:-5]
    return str_import_qualifiers


def sort_list(content_list):
    """
 
    """
    return sorted(content_list, key=lambda x: x[0].lower())


def write_xlsx_file(content_type, data_list, creds):
    """

    """
    file = gspread.authorize(creds)
    workbook = file.open("O11y Out of the Box Inventory Test")

    if content_type == 'navigator':
        sheet = workbook.worksheet('Navigators')

        # Clearing the Cells
        sheet.batch_clear(["A2:D120"])

        # Sort the list alphabetically
        data_list = sort_list(data_list)

        # Writing into GSheet
        sheet.update('A2:D120', data_list)
    elif content_type == 'dashboard':
        sheet = workbook.worksheet('Dashboards')

        # Clearing the Cells
        sheet.batch_clear(["A2:B200"])

        # Sort the list alphabetically
        data_list = sort_list(data_list)

        # Writing into GSheet
        sheet.update('A2:B200', data_list)
    elif content_type == 'detector':
        sheet = workbook.worksheet('Detectors')

        # Clearing the Cells
        sheet.batch_clear(["A2:B100"])

        # Sort the list alphabetically
        data_list = sort_list(data_list)

        # Writing into GSheet
        sheet.update('A2:B100', data_list)


def collect_content_name_importQualifiers_category_and_group(dest_list):
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

def parse_args():
  """
  
  """
  parser=argparse.ArgumentParser()
  parser.add_argument("-pki","--private_key_id",help="Service account's private key id")
  parser.add_argument("-pk","--private_key",help="Service account's private key")
  parser.add_argument("-ci","--client_id",help="Service account's client id")
  parser.add_argument("-ce","--client_email",help="Service account's client email")
  parser.add_argument("-pi","--project_id",help="Service account's project id")
  args=parser.parse_args()
  return args

def get_credentials():
  """
  
  """
  args = parse_args()
  cred_file = json.load(open('credentials.json'))
  cred_file["private_key_id"]= args.private_key_id
  encoded_private_key = args.private_key
  decoded_private_key = base64.b64decode(encoded_private_key).decode('utf-8')
  cred_file["private_key"] = decoded_private_key.replace("\\n", "\n")
  cred_file["client_email"]= args.client_email
  cred_file["client_id"]= args.client_id
  cred_file["project_id"]= args.project_id
  return cred_file

def main():
    """

    """
    cred_file = get_credentials()
    creds = ServiceAccountCredentials.from_json_keyfile_dict(cred_file)
    
    nav_files = collect_json_files("navigators/")
    nav_list = collect_content_name_importQualifiers_category_and_group(nav_files)
    write_xlsx_file("navigator", nav_list, creds)

    db_files = collect_json_files("group/")
    db_list = collect_content_name_importQualifiers_category_and_group(db_files)
    write_xlsx_file("dashboard", db_list, creds)

    dt_files = collect_json_files("detector/")
    dt_list = collect_content_name_importQualifiers_category_and_group(dt_files)
    write_xlsx_file("detector", dt_list, creds)


if __name__ == "__main__":
    main()
