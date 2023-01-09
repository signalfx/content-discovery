"""
File to update navigator's property into sentence case.

Steps of this script:
    1. Take the id from navigator file and get navigator's json from file itself.
        - Will save navigator_id and file_name
    2. Check all the possible properties which needs to be sentence case.
    3. With updated json call update API call.
    4. Export API call with the latest id and use that json to update the file.

    List of properties that we should make it sentence case.
        - name
        * uiModel.
            - displayName.
            - idName
            * listColumns.[].
                -displayName
            * metrics.[].
                - description
                - displayName
                - valueLabel
            * tooltipKeyList.[].
                - displayName
        - o11yMetricName        **************
        - o11yProductName       **************

        - navigatorCategoryDisplayName - Skip
        - navigatorCategoryGroupDisplayName - skip
        - singleHostSystemDashboardName ?? -- Skip
        - systemDashboardName ?? -- Skip

        **description: Check if it visible any where in UI if so update it to sentence case.

        ==Make sure use MSB id to update and get id for each navigator while traversing.
        ==Export json and write to the file. (Make sure to use indent=2 in json)
        ==Add support of arg parser.

"""
import json
import logging
import os
import time
import requests
from pathlib import Path

logging.basicConfig(filename="validate_navigator_py.log",
                    format='%(asctime)s %(message)s',
                    filemode='w')


class NavigatorSentenceCase:
    """
    To make sentence case navigator json.
    """

    def __init__(self):
        """
        Variable initialization
        """
        self.abs_path = ""
        self.folder_name = ""
        self.navigator_data = {}
        self.sentence_case_list = {}
        self.file_name = ""
        self.without_sentence_case = {}
        self.each_folder_sentence_case = {}
        self.new_updated_sentence_case = {}
        self.new_each_folder_sentence_case = {}
        self.old_each_folder_sentence_case = {}
        self.PRD_NAVIGATOR_API_URL = "https://app.signalfx.com/v2/navigator/{}"
        self.TST_NAVIGATOR_API_URL = "https://o11ytest.lab0.signalfx.com/v2/navigator/{}"
        self.PRD_X_SF_TOKEN = "1IqMUJ17SgN_pbXik61Pnw"
        self.TST_X_SF_TOKEN = "hDweyS-bM1Dnc7OvWV4OtQ"
        self.NAVIGATOR_ID = ""

    def list_json_files(self):
        """
        Get list of json files.
        """
        json_files = []
        print(self.abs_path)
        for (_, _, list_filenames) in os.walk(self.abs_path):
            for file_name in list_filenames:
                if file_name.endswith(".json"):
                    json_files.append(file_name)
        return json_files

    def total_navigator_count(self):
        """
        Sentence Case navigator.
        """
        # Folder name
        # self.folder_name = input("Enter your folder name to sentence case navigator(s).")
        # absolute path
        # Get the list of directory and absolute path of the file/folder
        dir_path = Path(__file__).parent.parent.joinpath('navigators')
        print(dir_path)
        # dir_path = os.path.dirname(__file__)
        self.abs_path = dir_path
        folder_list = [name for name in os.listdir(self.abs_path) if os.path.isdir(os.path.join(self.abs_path, name))]
        print(folder_list)
        # Traverse through each folder of navigators
        cnt = 0
        for folder_name in folder_list:
                # print(folder_name)
            # Todo: Add support of arg parser with folder name of navigator
            # if folder_name == 'RabbitMQ':
                self.folder_name = folder_name
                # Get list of json file
                self.abs_path = os.path.join(dir_path, self.folder_name)
                json_files = self.list_json_files()
                self.each_folder_sentence_case = {}

                # Go through each navigator json
                for file_name in json_files:
                    # Todo: Add support of arg parser with file name of navigator
                    # if file_name == "vsphere vms.json":
                        self.file_name = file_name
                        print(file_name)
                        # Read file json
                        with open(os.path.join(self.abs_path, file_name), 'r') as file:
                            data = json.load(file)
                            self.navigator_data = data.get('navigatorExport').get('navigator')
                            if self.navigator_data.get('sites') != 'signalview' and \
                                    self.navigator_data.get('navigatorType') in ["elemental", "list"] and \
                                    self.navigator_data.get('uiModel').get('o11yProductName') is not None:
                                cnt+=1
                                print(self.navigator_data.get('uiModel').get('o11yProductName'))
                        # if self.navigator_data.get('navigatorType') not in ["elemental", "list"] \
                        #         or self.navigator_data.get('sites') == 'signalview' \
                        #         or self.navigator_data.get('uiModel').get('o11yProductName') is None:
                        #     # Skip if navigator type is not elemental of list
                        #     continue
                        # else:
                        #     cnt += 1
                        #     print("\t",data.get('navigatorExport').get('navigator').get('name'))
        print(cnt)

    def sentence_case_navigator(self):
        """
        Sentence Case navigator.
        """
        # Folder name
        # self.folder_name = input("Enter your folder name to sentence case navigator(s).")
        # absolute path
        # Get the list of directory and absolute path of the file/folder
        dir_path = os.path.dirname(__file__)
        self.abs_path = os.path.join(dir_path, self.folder_name)
        folder_list = [name for name in os.listdir(self.abs_path) if os.path.isdir(os.path.join(self.abs_path, name))]

        # Traverse through each folder of navigators
        for folder_name in folder_list:
            # print(folder_name)
            # Todo: Add support of arg parser with folder name of navigator
            if folder_name == 'Google Cloud Platform':
                self.folder_name = folder_name
                # Get list of json file
                self.abs_path = os.path.join(dir_path, self.folder_name)
                json_files = self.list_json_files()
                self.each_folder_sentence_case = {}

                # Go through each navigator json
                for file_name in json_files:
                    # Todo: Add support of arg parser with file name of navigator
                    if file_name == "gcp storage.json":
                        self.file_name = file_name

                        # Read file json
                        with open(os.path.join(self.abs_path, file_name), 'r') as file:
                            data = json.load(file)
                        self.navigator_data = data.get('navigatorExport').get('navigator')
                        self.NAVIGATOR_ID = data.get('navigatorExport').get('navigator').get('id')

                        if self.navigator_data.get('navigatorType') not in ["elemental", "list"] \
                                or self.navigator_data.get('sites') == 'signalview' \
                                or self.navigator_data.get('uiModel').get('o11yProductName') is None:
                            print(f"This navigator will get skip: {file_name}")
                            # Skip if navigator type is not elemental of list
                            continue
                        else:
                            # Update the sentence case json
                            logging.info(f"Found the navigator data: {self.navigator_data}")
                            # self.prepare_data_json()
                            self.update_sentence_case_json_with_case()
                        # print(self.navigator_data)
                        # print(json.dumps(self.navigator_data))

                        # Todo: Update with support of flag if we want to update the navigator with sentence case and
                        #  export or only export navigator json
                        # #  Update the content on MSB and export the content in respective json file
                        self.update_navigator_api()
                        # For safer side to get the latest exported json
                        print("Waiting for 2 seconds.")
                        time.sleep(2)
                        # Export navigator json api call
                        self.export_navigator_api()

    def update_navigator_api(self):
        """
        To update the navigator on MSB.
        """
        url = self.PRD_NAVIGATOR_API_URL.format(self.NAVIGATOR_ID)
        payload = json.dumps(self.navigator_data)
        # print(payload)

        headers = {
            'x-sf-token': self.PRD_X_SF_TOKEN,
            'Content-Type': 'application/json'
        }

        response = requests.put(url, headers=headers, data=payload)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to update navigator {self.NAVIGATOR_ID}: {response.text}")

        print(response.text)

    def export_navigator_api(self):
        """
        To export the navigator.
        """
        url = self.PRD_NAVIGATOR_API_URL.format(self.NAVIGATOR_ID + '/export')
        # url = self.TST_NAVIGATOR_API_URL.format(self.NAVIGATOR_ID + '/export')
        headers = {
            'X-SF-TOKEN': self.PRD_X_SF_TOKEN
            # 'X-SF-TOKEN': self.TST_X_SF_TOKEN
        }

        response = requests.request("GET", url, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to update navigator {self.NAVIGATOR_ID}: {response.text}")
        print(response.json())
        with open(os.path.join(self.abs_path, self.file_name), 'w') as f:
            json.dump(response.json(), f, indent=2)

    def update_sentence_case_json_with_case(self):
        """
        Update the json object with sentence casing.
        """
        # Get the old navigator name
        old_name = self.navigator_data.get('name')

        # Update old navigator data with updated sentence case value.
        self.navigator_data['name'] = self.get_sentence_case([old_name])[0]

        # Get uiModel object
        uiModel = self.navigator_data.get('uiModel')

        uiModel_displayName = uiModel.get('displayName')
        self.navigator_data['uiModel']['displayName'] = self.get_sentence_case([uiModel_displayName])[0]

        uiModel_idName = uiModel.get('idName')
        self.navigator_data['uiModel']['idName'] = self.get_sentence_case([uiModel_idName])[0]

        uiModel_o11yMetricName = uiModel.get('o11yMetricName')
        self.navigator_data['uiModel']['o11yMetricName'] = self.get_sentence_case([uiModel_o11yMetricName])[0]

        uiModel_o11yProductName = uiModel.get('o11yProductName')
        self.navigator_data['uiModel']['o11yProductName'] = self.get_sentence_case([uiModel_o11yProductName])[0]

        uiModel_listColumns__displayName = []
        list_columns = uiModel.get('listColumns')
        for index, column in enumerate(list_columns):
            self.navigator_data['uiModel']['listColumns'][index]['displayName'] = \
                self.get_sentence_case([column.get('displayName')])[0]
            uiModel_listColumns__displayName.append(column.get('displayName'))

        uiModel_metrics__description = []
        uiModel_metrics__displayName = []
        uiModel_metrics__valueLabel = []
        list_desc = uiModel.get('metrics')
        for index, desc in enumerate(list_desc):
            uiModel_metrics__description.append(desc.get('description'))
            self.navigator_data['uiModel']['metrics'][index]['description'] = \
                self.get_sentence_case([desc.get('description')])[0]

            uiModel_metrics__displayName.append(desc.get('displayName'))
            self.navigator_data['uiModel']['metrics'][index]['displayName'] = \
                self.get_sentence_case([desc.get('displayName')])[0]

            uiModel_metrics__valueLabel.append(desc.get('valueLabel'))
            self.navigator_data['uiModel']['metrics'][index]['valueLabel'] = \
                self.get_sentence_case([desc.get('valueLabel')])[0]

        uiModel_tooltipKeyList__displayName = []
        tooltips = uiModel.get('tooltipKeyList')
        if tooltips:
            # Go through each tooltip and update the display name with sentence case
            for index, tooltip in enumerate(tooltips):
                uiModel_tooltipKeyList__displayName.append(tooltip.get('displayName'))
                self.navigator_data['uiModel']['tooltipKeyList'][index]['displayName'] = \
                    self.get_sentence_case([tooltip.get('displayName')])[0]

        # To compare old and sentence cased filed created this dict.
        self.new_each_folder_sentence_case.update({self.file_name:
            {
                "name": self.get_sentence_case([old_name])[0],
                "uiModel_o11yMetricName": self.get_sentence_case([uiModel_o11yMetricName])[0],
                "uiModel_o11yProductName": self.get_sentence_case([uiModel_o11yProductName])[0],
                "uiModel_displayName": self.get_sentence_case([uiModel_displayName])[0],
                "uiModel_idName": self.get_sentence_case([uiModel_idName])[0],
                "uiModel_listColumns__displayName": self.get_sentence_case(uiModel_listColumns__displayName),
                "uiModel_metrics__description": self.get_sentence_case(uiModel_metrics__description),
                "uiModel_metrics__displayName": self.get_sentence_case(uiModel_metrics__displayName),
                "uiModel_metrics__valueLabel": self.get_sentence_case(uiModel_metrics__valueLabel),
                "uiModel_tooltipKeyList__displayName": self.get_sentence_case(uiModel_tooltipKeyList__displayName)
            }
        })
        self.old_each_folder_sentence_case.update({self.file_name:
            {
                "name": old_name,
                "uiModel_o11yMetricName": uiModel_o11yMetricName,
                "uiModel_o11yProductName": uiModel_o11yProductName,
                "uiModel_displayName": uiModel_displayName,
                "uiModel_idName": uiModel_idName,
                "uiModel_listColumns__displayName": uiModel_listColumns__displayName,
                "uiModel_metrics__description": uiModel_metrics__description,
                "uiModel_metrics__displayName": uiModel_metrics__displayName,
                "uiModel_metrics__valueLabel": uiModel_metrics__valueLabel,
                "uiModel_tooltipKeyList__displayName": uiModel_tooltipKeyList__displayName
            }
        })

        self.new_updated_sentence_case.update({self.folder_name: self.new_each_folder_sentence_case})

    def prepare_data_json(self):
        """

        """
        old_name = self.navigator_data.get('name')

        new_name = self.navigator_data.get('name').capitalize()
        self.navigator_data['name'] = new_name
        print("==================")
        uiModel = self.navigator_data.get('uiModel')
        uiModel_displayName = uiModel.get('displayName')
        uiModel_idName = uiModel.get('idName')

        uiModel_listColumns__displayName = []
        list_columns = uiModel.get('listColumns')
        for column in list_columns:
            uiModel_listColumns__displayName.append(column.get('displayName'))

        uiModel_metrics__description = []
        uiModel_metrics__displayName = []
        uiModel_metrics__valueLabel = []
        list_desc = uiModel.get('metrics')
        for desc in list_desc:
            uiModel_metrics__description.append(desc.get('description'))
            uiModel_metrics__displayName.append(desc.get('displayName'))
            uiModel_metrics__valueLabel.append(desc.get('valueLabel'))

        uiModel_tooltipKeyList__displayName = []
        tooltips = uiModel.get('tooltipKeyList')
        if tooltips:
            for tooltip in tooltips:
                uiModel_tooltipKeyList__displayName.append(tooltip.get('displayName'))
        self.each_folder_sentence_case.update({self.file_name:
            {
                "name": old_name, "uiModel_displayName": uiModel_displayName,
                "uiModel_idName": uiModel_idName,
                "uiModel_listColumns__displayName": uiModel_listColumns__displayName,
                "uiModel_metrics__description": uiModel_metrics__description,
                "uiModel_metrics__displayName": uiModel_metrics__displayName,
                "uiModel_metrics__valueLabel": uiModel_metrics__valueLabel,
                "uiModel_tooltipKeyList__displayName": uiModel_tooltipKeyList__displayName
            }
        })

        self.without_sentence_case.update({self.folder_name: self.each_folder_sentence_case})

    def get_sentence_case(self, input_str_list: list):
        """

        """
        output_str_list = []
        for input_str in input_str_list:
            print(input_str)
            print()
            output = ""

            is_first_char = True
            is_space_gt_1 = False
            if input_str is not None:
                for c in input_str:
                    # To include the case in which sentence starting with '#' e.g # Clusters
                    if is_first_char and c in '#':
                        is_first_char = True

                    # To make it upper case if it's 1st character and not space
                    elif is_first_char and not c.isspace():
                        c = c.upper()
                        is_first_char = False

                    # To include all the case ending with .!?|# and starting new sentence after that.
                    elif not is_first_char and c in ".!?|#":
                        if is_space_gt_1:
                            is_first_char = True

                    # All other char should be in lower
                    else:
                        c = c.lower()

                    # Every time we are checking
                    if c.isspace():
                        is_space_gt_1 = True

                    output = output + c
            # print("==================================Before replacement special word=============================================")
            # print(output)
            # print("===============================================================================")
            output = self.replace_special_words(output)
            print(output)
            print("===============================================================================")
            output_str_list.append(output)
        return output_str_list

    @staticmethod
    def replace_special_words(input_str: str):
        # print(input_str)
        # print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        special_words = {'mts': 'MTS', 'epm': 'EPM', 'iis': 'IIS', 'http': 'HTTP', 'vm': 'VM', 'vms': 'VMs',
                         'i/o': 'I/O', 'io': 'I/O', 'mmapv1': 'MMAPv1',
                         'cpu': 'CPU', 'sql': 'SQL', 'db': 'DB', 'gb': 'GB', 'os': 'OS', 'jmx': 'JMX',
                         'jvm': 'JVM', 'pga': 'PGA', 'vcpu': 'vCPU',
                         'tcp': 'TCP', 'nginx': 'NGINX', 'mysql': 'MySQL', 'dynamodb': 'DynamoDB', 'rds': 'RDS',
                         'ram': 'RAM', 'sqs': 'SQS', 'alb': 'ALB', 'lcu': 'LCU', 'ebs': 'EBS', 'sns': 'SNS',
                         'ecs': 'ECS', 'aws': 'AWS', 'vsphere': 'vSphere', 'vcenter': 'vCenter', 'signalfx': 'SignalFx',
                         'mongodb': 'MongoDB', 'api': 'API', 'isr': 'ISR', 'cms': 'CMS', 'parnew': 'ParNew',
                         'tls': 'TLS', 'apache': 'Apache', 'solr': 'Solr', 'opsworks': 'OpsWorks',
                         'telegraf': 'Telegraf', 'gc': 'GC', 'znodes': 'ZNodes', 'zookeeper': 'ZooKeeper',
                         'redis': 'Redis',
                         'erlang': 'Erlang', 'rabbitmq': 'RabbitMQ', 'dml': 'DML', 'npm': 'NPM', 'permgen': 'PermGen'}
        # new_updated_str = ""
        # for word_input_str in input_str.split(' '):
        #     with_dot = False
        #
        #     # print(f"updated word input str: {updated_word_input_str}")
        #     latest_word = ""
        #     for special_word_key in special_words.keys():
        #         if special_word_key == word_input_str or special_word_key.capitalize() == word_input_str:
        #             latest_word = special_words.get(special_word_key)
        #         updated_word_input_str = word_input_str.split(".")[0]
        #         if special_word_key == updated_word_input_str or special_word_key.capitalize() == updated_word_input_str:
        #             latest_word = special_words.get(special_word_key)
        #         if len(word_input_str.split(".")) > 1:
        #             with_dot = True
        #     if with_dot:
        #         if latest_word:
        #             new_updated_str += latest_word+". "
        #         else:
        #             new_updated_str += word_input_str+". "
        #     else:
        #         if latest_word:
        #             new_updated_str += latest_word+" "
        #         else:
        #             new_updated_str += word_input_str+" "
        updated_str = ""
        for word_input_str in input_str.split(' '):
            flag = False
            for special_word_key in special_words.keys():
                if special_word_key == word_input_str.lower():
                    word_input_str = special_words[special_word_key]
                    updated_str += (word_input_str + ' ')
                    flag = True
                elif (special_word_key + '.') == word_input_str.lower():
                    word_input_str = special_words[special_word_key] + '.'
                    updated_str += (word_input_str + ' ')
                    flag = True
                elif (special_word_key + ':') == word_input_str.lower():
                    word_input_str = special_words[special_word_key] + ':'
                    updated_str += (word_input_str + ' ')
                    flag = True
                break
            if not flag:
                updated_str += (word_input_str + ' ')
        new_updated_str = updated_str.strip()
        input_str = new_updated_str
        # print(f"New updated str: {new_updated_str}")
        # print(f"New updated str with strip: {new_updated_str.strip()}")
        special_multiple_words = {'(program global area)': '(Program Global Area)',
                                  'delete commands': 'DELETE commands', 'select commands': 'SELECT commands',
                                  'update commands': 'UPDATE commands', 'insert commands': 'INSERT commands',
                                  "\"not found\"": "\"Not Found\""}
        for special_word_key in special_multiple_words.keys():
            if special_word_key in input_str:
                input_str = input_str.replace(special_word_key, special_multiple_words.get(special_word_key))
            elif special_word_key.capitalize() in input_str:
                input_str = input_str.replace(special_word_key.capitalize(),
                                              special_multiple_words.get(special_word_key))
        # print(input_str)
        # print("==============================================================================================================")
        return input_str


# NavigatorSentenceCase().get_sentence_case(["This metric shows the number of IO operations / sec (read and write operations) of databases. Darker colors indicate higher relative values."])
# NavigatorSentenceCase().replace_special_words("This metric shows the number of io operations / sec (read and write operations).")
# NavigatorSentenceCase().replace_special_words("This metric shows the number of operations io operations / sec (read and write operations).")
# NavigatorSentenceCase().sentence_case_navigator()
NavigatorSentenceCase().total_navigator_count()


# NavigatorSentenceCase().replace_special_words("This is os.  this ")

# NavigatorSentenceCase().get_sentence_case(["This metric shows the total number of garbage collection events for GC CMS per sec. GC CMS metric will not be available for Java Version 9.0 and above as it has been deprecated. Darker colors indicate higher relative values."])
