import json
import os
from xlsxwriter import Workbook

#GSheet setup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("navigator-list.json",scope)
client = gspread.authorize(creds)

def collect_nav_files():
    dest_list = []
    for dir, _, files in os.walk("navigators/"):
        for filename in files:
            if filename.endswith('.json'):
              with open(os.path.abspath(os.path.join(dir, filename))) as file:
                navJson = json.load(file)
                navJson = navJson['navigatorExport']['navigator']
                keys = navJson['uiModel'].keys()
                #To ignore the navigators with architectural type, and navigators with no Name(not getting displayed) and navigators with name "Nodes", "Pods", and "Containers" (Because older version file is also present in the repo and we have to ignore those) and ignore navigators with sites = "signalview" and ignored navigators that are unreleased
                if 'o11yProductName' in keys and (navJson['navigatorType']!='architectural') and (navJson['uiModel']['o11yProductName'] != None and navJson['uiModel']['o11yProductName'] != "Pods" and navJson['uiModel']['o11yProductName'] != "Containers" and navJson['uiModel']['o11yProductName'] != "Nodes") and (navJson['sites'] != "signalview") and (not navJson['uiModel']['unreleased']):
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
    # To get the importQualifier
    for import_qualifier in nav_import_qualifiers:
      str_import_qualifiers += import_qualifier['metric'] + " "

      # To get the filters
      for value_property in import_qualifier.get('filters'):
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
      #To remove last & symbol
      str_import_qualifiers = str_import_qualifiers[:-3]
      str_import_qualifiers += ";\n"
    print(str_import_qualifiers)
    return str_import_qualifiers


def write_xlsx_file(nav_data_list):
    """

    """
    
    #Add GSheet logic - Create Google Sheet
    
    ordered_list=["Name", "importQualifiers", "Category Group DisplayName", "Category DisplayName"] # List object calls by index, but the dict object calls items randomly

    sheet = client.open("OOTB Navigators").sheet1

    # wb = Workbook("OOTB Navigators.xlsx")
    # ws = wb.add_worksheet("Navigators") # Or leave it blank. The default name is "Sheet 1"

    # first_row=0
    # bold = wb.add_format({'bold': True,'font':'georgia'})
    # bold.set_font_size(12)
    # font = wb.add_format({'font':'georgia'})
    # font.set_font_size(10)
    # ws.set_column('A:A', 20)
    # ws.set_column('B:B', 90)
    # ws.set_column('C:C', 30)
    # ws.set_column('D:D', 30)
    for header in ordered_list:
        col=ordered_list.index(header) # We are keeping order.
        sheet.insert_row(header) # We have written first row which is the header of worksheet also.

    # row=1
    # for nav_data in nav_data_list:
    #     for _key,_value in nav_data.items():
    #         col=ordered_list.index(_key)
    #         ws.write(row,col,_value,font)
    #     row+=1 #enter the next row
    # wb.close()

def collect_nav_name_desc_and_type(dest_list):
    """

    """
    nav_collections = []
    for dest_path in dest_list:
        print("---------")
        print(dest_path)
        with open(dest_path, 'r') as nav_file:
            data = json.load(nav_file)
            navJson = data['navigatorExport']['navigator']
            nav_collections.append({
                'Name': navJson['uiModel']['o11yProductName'],
                'importQualifiers': prepare_import_qualifiers(navJson['importQualifiers']),
                'Category DisplayName': navJson.get('navigatorCategory') if navJson.get('navigatorCategory') is not None else "Others",
                'Category Group DisplayName': navJson.get('navigatorCategoryGroupDisplayName') if navJson.get('navigatorCategoryGroupDisplayName') is not None else "Others"
            })
    return nav_collections

def write_readmemd_file():
    """

    """
    nav_files = collect_nav_files()
    nav_list = collect_nav_name_desc_and_type(nav_files)
    write_xlsx_file(nav_list)

write_readmemd_file()

