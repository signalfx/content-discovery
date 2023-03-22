import json
import os
from xlsxwriter import Workbook

def collect_json_files(path):
    dest_list = []
    if path == "navigators/":
      for dir, _, files in os.walk(path):
          for filename in files:
              if filename.endswith('.json'):
                with open(os.path.abspath(os.path.join(dir, filename))) as file:
                  navJson = json.load(file)
                  navJson = navJson['navigatorExport']['navigator']
                  keys = navJson['uiModel'].keys()
                  #To ignore the navigators with architectural type, and navigators with no Name(not getting displayed) and navigators with name "Nodes", "Pods", and "Containers" (Because older version file is also present in the repo and we have to ignore those) and ignore navigators with sites = "signalview" and ignored navigators that are unreleased
                  if 'o11yProductName' in keys and (navJson['navigatorType']!='architectural') and (navJson['uiModel']['o11yProductName'] != None and navJson['uiModel']['o11yProductName'] != "Pods" and navJson['uiModel']['o11yProductName'] != "Containers" and navJson['uiModel']['o11yProductName'] != "Nodes") and (navJson['sites'] != "signalview") and (not navJson['uiModel']['unreleased']):
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
    ##########Handle or add "and" "or" words and add "*" if null in values
    
    str_import_qualifiers = ""
    dummy_import_qualifiers = ""
    # To get the importQualifier
    for import_qualifier in nav_import_qualifiers:
      str_import_qualifiers += import_qualifier['metric'] + " "

      # To get the filters
      for value_property in import_qualifier.get('filters'):
          if 'property' in value_property.keys():
            str_import_qualifiers += "(" + (value_property.get('property') if value_property.get('property') != "" else "*" )
            if str_import_qualifiers[-1] == '*':
                str_import_qualifiers+=") & "
                continue
            prop_operation = "!=" if value_property["not"] else "="
            str_import_qualifiers += (prop_operation) + " "

          # To get the list of values appended with | (pipe)
            list_values = ""
            for prop_value in value_property.get('values'):
              list_values += prop_value + " | "
          #Check if the list_values is null, replace it with *
            if list_values == "":
              list_values = "* | "
          # To remove last pipe symbol
            list_values = list_values[:-3]
            str_import_qualifiers += list_values + ")" + " & "
      if str_import_qualifiers == dummy_import_qualifiers + import_qualifier['metric'] + " ":
          str_import_qualifiers += "(*)"
      else:
          #To remove last & symbol
          str_import_qualifiers = str_import_qualifiers[:-3]
      str_import_qualifiers += ";  OR\n"
      dummy_import_qualifiers = str_import_qualifiers
    str_import_qualifiers = str_import_qualifiers[:-5]
    print(str_import_qualifiers)
    return str_import_qualifiers


def write_xlsx_file(type, data_list):
    """

    """
    ordered_list=""
    wb = Workbook("O11y Out of the Box Inventory.xlsx")
    if type == 'navigator':
      ordered_list=["Name", "importQualifiers", "Category Group DisplayName", "Category DisplayName"]
      ws = wb.add_worksheet("Navigators")
      ws.set_column('A:A', 20)
      ws.set_column('B:B', 90)
      ws.set_column('C:C', 30)
      ws.set_column('D:D', 30)
    elif type == 'dashboard':
      ordered_list=["Name","importQualifiers"]
      ws = wb.add_worksheet("Dashboards")
      ws.set_column('A:A', 30)
      ws.set_column('B:B', 110)
    elif type == 'detector':
      ordered_list=["Name","importQualifiers"]
      ws = wb.add_worksheet("Detectors")
      ws.set_column('A:A', 60)
      ws.set_column('B:B', 110)

    first_row=0
    bold = wb.add_format({'bold': True,'font':'georgia'})
    bold.set_font_size(12)
    font = wb.add_format({'font':'georgia'})
    font.set_font_size(10)
    for header in ordered_list:
        col=ordered_list.index(header) # We are keeping order.
        ws.write(first_row,col,header,bold) # We have written first row which is the header of worksheet also.

    row=1
    for nav_data in data_list:
        for _key,_value in nav_data.items():
            col=ordered_list.index(_key)
            ws.write(row,col,_value,font)
        row+=1 #enter the next row
    wb.close()

def collect_content_name_desc_and_type(dest_list):
    """

    """
    collections = []
    if 'content-discovery/navigators/' in dest_list[0]:
      for dest_path in dest_list:
          print("---------")
          print(dest_path)
          with open(dest_path, 'r') as nav_file:
              data = json.load(nav_file)
              navJson = data['navigatorExport']['navigator']
              collections.append({
                  'Name': navJson['uiModel']['o11yProductName'],
                  'importQualifiers': prepare_import_qualifiers(navJson['importQualifiers']),
                  'Category DisplayName': navJson.get('navigatorCategory') if navJson.get('navigatorCategory') is not None else "Others",
                  'Category Group DisplayName': navJson.get('navigatorCategoryGroupDisplayName') if navJson.get('navigatorCategoryGroupDisplayName') is not None else "Others"
              })
    elif 'content-discovery/group/' in dest_list[0]:
      for dest_path in dest_list:
          print("---------")
          print(dest_path)
          with open(dest_path, 'r') as db_file:
              data = json.load(db_file)
              collections.append({
                  'Name': data['groupExport']['group']['name'],
                  'importQualifiers': prepare_import_qualifiers(data['groupExport']['group']['importQualifiers']),
              })
    elif 'content-discovery/detector/' in dest_list[0]:
      for dest_path in dest_list:
          print("---------")
          print(dest_path)
          with open(dest_path, 'r') as db_file:
              data = json.load(db_file)
              collections.append({
                  'Name': data['detectorExport']['detector']['name'],
                  'importQualifiers': prepare_import_qualifiers(data['detectorExport']['detector']['importQualifiers']),
              })
    return collections

def write_readmemd_file(option):
    """

    """
    match option:
      case '1':
        nav_files = collect_json_files("navigators/")
        nav_list = collect_content_name_desc_and_type(nav_files)
        write_xlsx_file("navigator", nav_list)
      case '2':
        db_files = collect_json_files("group/")
        db_list = collect_content_name_desc_and_type(db_files)
        write_xlsx_file("dashboard", db_list)
        return ""
      case '3':
        dt_files = collect_json_files("detector/")
        dt_list = collect_content_name_desc_and_type(dt_files)
        write_xlsx_file("detector", dt_list)
        return ""

write_readmemd_file('3')