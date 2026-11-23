import argparse
import json
import time
import requests
import os
import re

def collect_json_files(path):
        """
        Collect all list of json files based on given path.
        """
        dest_list = []
        if path == "navigators/":
            for dir, _, files in os.walk(path):
                print(path)
                for filename in files:
                    if filename.endswith('.json'):
                        dest_list.append(os.path.abspath(os.path.join(dir, filename)))
        # print(dest_list)
        return dest_list
                                

def extract_filters(navigator_paths):
    """
    Extract the filters for signalflow template
    """

    filter_file = {}
    multiple_signal_flow_dict = {}
    navigator_file_name = set()
    for navigator_path in navigator_paths:
        data = {}
        with open(navigator_path, 'r') as file:
            data = json.load(file)
            if 'content-discovery/navigators' in navigator_path:
                nav_json = data['navigatorExport']['navigator']
                metric_list = nav_json['uiModel']['metrics']
                filter_array_object= {}
                multiple_signal_flow = []
                
                for index, metric in enumerate(metric_list):
                    template = metric['job']['template']
                    varname = metric['job']['varName']
                    filters_regex = r"filter\(.*?\)|not filter\(.*?\)"
                    filter_string = r"filter.*=.*{{\/filter}}.*?"
                    regex = r"filter\((.*)\)"

                    if template.count("data(") == 1:
                        matches = re.findall(filters_regex, template)
                        filter_object_array = []
                        match_missing = False
                        for match in matches:
                            filter_exists = False
                            filters = re.findall(regex, match)
                            if filters:
                                split_matches = [filter.strip().replace("'", '') for filter in filters[0].split(',')]

                            porpertyValue = ""
                            if len(split_matches) > 2:
                                if 'match_missing=True' in split_matches[-1]:
                                    multiple_signal_flow.append(data['navigatorExport']['navigator']['uiModel']['metrics'][index]["id"])
                                    match_missing = True
                                    break
                                else:
                                    propertyValue = split_matches[1:]
                            else:
                                propertyValue = split_matches[1].strip().replace("\"", '')

                            if match.count("not"):
                                filter_exists = True

                            filter_object_array.append({
                                "type": "property",
                                "property": split_matches[0].strip().replace("\"", ''),
                                "propertyValue": propertyValue,
                                "not": filter_exists
                            })
                        updated_template = re.sub(filter_string, 'filter={{{filter}}}{{/filter}}', template)
                        updated_template_regex = re.findall(r"data\(([^,]+)", updated_template)

                        if "{{#filter}}" in updated_template_regex[0]:
                            updated_template = re.sub(filter_string, 'filter={{{filter}}}{{/filter}}', template)
                        else:
                            updated_template = re.sub(filter_string, 'filter={{{filter}}}{{/filter}}', template)
                            updated_template = re.sub(r"data\(([^,]+)", "data("+updated_template_regex[0]+"{{#filter}}", updated_template)
                        filter_array_object[varname] = {"template": updated_template, "original_template": template,  "filters": filter_object_array}
                        
                        
                        if not match_missing and filter_object_array:
                            existing_filters = data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['filters']
                            data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['template'] = updated_template
                            if existing_filters is None:
                                data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['filters'] = []
                            data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['filters'].extend(filter_object_array)
                            navigator_file_name.add(navigator_path)


                    else:
                        # if not data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['filters']:
                        multiple_signal_flow.append(data['navigatorExport']['navigator']['uiModel']['metrics'][index]["id"])

                        
                        # matches = re.findall(filters_regex, template)
                        # filter_object_array = []
                        # filter_string = "filter=.*?{{\/filter}}.*?"
                        # property_dict = {}
                        # property_value_dict = {}
                        # for match in matches:
                        #     filter_exists = "false"
                        #     filters = re.findall(regex, match)
                        #     if filters:
                        #         split_matches = [filter.strip().replace("'", '') for filter in filters[0].split(',')]

                        #     porpertyValue = ""
                        #     if len(split_matches) > 2:
                        #         if 'match_missing=True' in split_matches[-1]:
                        #             if len(split_matches[1:-1]) > 2:
                        #                 propertyValue = split_matches[1:-1]
                        #             else:
                        #                 propertyValue = split_matches[1].strip().replace("\"", '')
                        #         else:
                        #             propertyValue = split_matches[1:]
                        #     else:
                        #         propertyValue = split_matches[1].strip().replace("\"", '')

                        #     if match.count("not"):
                        #         filter_exists = "true"
                            
                        #     if split_matches[0].strip().replace("\"", '') not in property_dict.keys():
                        #         property_dict[split_matches[0].strip().replace("\"", '')] = 0
                        #     if propertyValue not in property_value_dict:
                        #         property_value_dict[propertyValue] = 0
                        
                        #     property_dict[split_matches[0].strip().replace("\"", '')] += 1 
                        #     property_value_dict[propertyValue] += 1
                        #     # print(property_dict[split_matches[0].strip().replace("\"", '')])

                        #     if property_dict[split_matches[0].strip().replace("\"", '')] == 1 and property_value_dict[propertyValue] == 1:
                        #         # print(split_matches[0].strip().replace("\"", ''), propertyValue)
                        #         filter_object_array.append({
                        #             "type": "property",
                        #             "property": split_matches[0].strip().replace("\"", ''),
                        #             "propertyValue": propertyValue,
                        #             "not": filter_exists
                        #         })
                        # for key, value in property_value_dict.items():
                        #         # print(key, value)
                        #         # print(template.count("data("))
                        #         if value % 2 != 0:
                        #             # print(template.count("data("))
                        #             filter_object_array = []
                        #         else:
                        #             # print(property_value_dict)
                        #             updated_template = re.sub(filter_string, 'filter={{{filter}}}{{/filter}}', template)
                        #             test = re.findall(r"data\(([^,]+)", updated_template)

                        #             if "{{#filter}}" in test[0]:
                        #                 updated_template = re.sub(filter_string, 'filter={{{filter}}}{{/filter}}', template)
                        #             else:
                        #                 updated_template = re.sub(filter_string, 'filter={{{filter}}}{{/filter}}', template)
                        #                 updated_template = re.sub(r"data\(([^,]+)", "data("+test[0]+"{{#filter}}", updated_template)
                        #         filter_array_object[varname] = {"template": updated_template, "original_template": template,  "filters": filter_object_array}

                        # data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['template'] = updated_template
                        # data['navigatorExport']['navigator']['uiModel']['metrics'][index]['job']['filters'] = filter_object_array

                if multiple_signal_flow:
                    multiple_signal_flow_dict[navigator_path] = multiple_signal_flow

                                
                            

                filter_file[navigator_path] = filter_array_object

        
        with open(navigator_path, 'w') as file:
            json.dump(data, file, indent = 2)
        with open("multiple_signal_flow.json", 'w') as file:
            json.dump(multiple_signal_flow_dict, file, indent = 2)
        with open("navigator_file.json", "w") as file:
            json.dump({"paths": list(navigator_file_name)}, file, indent=2)

    # with open("data.json", "w") as json_file:
    #     json.dump(filter_file, json_file, indent = 2)


if __name__ == "__main__":
    
    extract_filters(collect_json_files('navigators/'))
