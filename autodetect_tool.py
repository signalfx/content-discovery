#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
import re
import requests
import subprocess


SCRIPT_DIR = Path(__file__).parent

ORIGIN_AUTODETECT = 'AutoDetect'
TOKEN_HEADER = 'X-SF-TOKEN'

RE_METRIC_PATTERN = re.compile(r'[a-zA-z0-9\.]+', re.DOTALL)


class DetectorScheme:
    ID = 'id'
    PROGRAM_TEXT = 'programText'
    NAME = 'name'
    DETECTOR_ORIGIN = 'detectorOrigin'
    PACKAGE_SPECIFICATION = 'packageSpecifications'
    IMPORT_QUALIFIERS = 'importQualifiers'
    RULES = 'rules'
    TIP = 'tip'
    RUNBOOK_URL = 'runbookUrl'


class DetectorExportScheme:
    DETECTOR_EXPORT = 'detectorExport'
    DETECTOR = 'detector'
    HASH_CODE = 'hashCode'


class DetectorExportState:
    ADD_NEW = 'ADD_NEW'
    UPDATE_EXISTING = 'UPDATE_EXISTING'
    SKIP_EXISTING = 'SKIP_EXISTING'
    SKIP_AUTODETECT = 'SKIP_AUTODETECT'


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class ValidationState:
    def __init__(self, passed, description):
        self.passed = passed
        self.description = description

    @classmethod
    def fail_validation(cls, description):
        return cls(False, description)

    @classmethod
    def pass_validation(cls, description):
        return cls(True, description)


class DetectorExportInfo:
    def __init__(self, detector, state, skip, skip_reason='', validation_results=[], export_path=None):
        self.detector = detector
        self.state = state
        self.skip = skip
        self.skip_reason = skip_reason
        self.validation_results = validation_results
        self.export_path = export_path

    def is_valid(self):
        if self.state in [DetectorExportState.ADD_NEW, DetectorExportState.UPDATE_EXISTING] and self.skip:
            return False
        else:
            return True

    def message_prefix_by_state(self):
        color = Colors.WARNING
        message_level = "Info"
        if self.state in [DetectorExportState.ADD_NEW, DetectorExportState.UPDATE_EXISTING]:
            if self.is_valid():
                message_level = "Ok"
                color = Colors.OKGREEN if self.state == DetectorExportState.ADD_NEW else Colors.OKBLUE
            else:
                message_level = "Error"
                color = Colors.FAIL

        return f"{color}[{message_level}][{self.state}]{Colors.ENDC}"

    def print(self):
        name = self.detector.get(DetectorScheme.NAME)
        detector_id = self.detector.get(DetectorScheme.ID)
        message_prefix = self.message_prefix_by_state()
        print(f'{message_prefix}[{detector_id}]: {name}')
        for validation_state in self.validation_results:
            validation_state_msg = self.validation_state_message(validation_state.passed, validation_state.description)
            print('\t' + validation_state_msg)
        print('\t' + '-'*40)
        if self.skip:
            summary_msg = self.validation_state_message(valid=False, desc=self.skip_reason)
            print('\t' + summary_msg)
        else:
            summary_msg = self.validation_state_message(valid=True, desc=f"All good. Export path: {self.export_path}")
            print("\t" + summary_msg)
        print("~" * 100)

    @classmethod
    def skip_autodetect(cls, detector):
        return cls(detector,
                   state=DetectorExportState.SKIP_AUTODETECT,
                   skip=True,
                   skip_reason="Only standard detectors can be exported")

    @classmethod
    def skip_no_changes(cls, detector):
        return cls(detector,
                   state=DetectorExportState.SKIP_EXISTING,
                   skip=True,
                   skip_reason="Hash code is equal. No changes for the detector")

    @classmethod
    def skip_validation_errors(cls, detector, state, validation_results):
        return cls(detector,
                   state=state,
                   skip=True,
                   skip_reason="Detector validation failed",
                   validation_results=validation_results)

    @classmethod
    def valid_export(cls, detector, state, validation_results, export_path):
        return cls(detector,
                   state=state,
                   skip=False,
                   validation_results=validation_results,
                   export_path=export_path)

    @staticmethod
    def validation_state_message(valid, desc):
        color = Colors.OKCYAN if valid else Colors.FAIL
        unicode_symbol = '\u2713' if valid else '\u2717'
        return f"{color}{unicode_symbol}{Colors.ENDC} {desc}"

    @staticmethod
    def print_summary(export_info_list):
        stats = {}
        for export_info in export_info_list:
            if export_info.is_valid():
                stats[export_info.state] = stats.get(export_info.state, 0) + 1
            else:
                stats["errors"] = stats.get("errors", 0) + 1
        print(stats)
        if stats.get(DetectorExportState.ADD_NEW, 0) > 0:
            print(f"{Colors.WARNING}[Warning] Please review import qualifiers, before committing changes. "
                  f"API used for that purpose doesn't support many complex scenarios{Colors.ENDC}")


def base_api_url_from_env(env: str) -> str:
    return f"https://api.{env}.signalfx.com/"


def get_token_from_file() -> str:
    try:
        token = (SCRIPT_DIR / ".token").read_text()
    except OSError:
        return None

    return token.strip()


def make_request(endpoint, realm, token, method="GET", headers={}, data=None, rsp_format='json'):
    base_url = base_api_url_from_env(env=realm)
    url = base_url + endpoint
    merged_headers = {
        TOKEN_HEADER: token,
        **headers
    }
    if method == "GET":
        rsp = requests.get(url, headers=merged_headers)
    elif method == "POST":
        if data is None:
            raise Exception("No data provided for POST request")
        rsp = requests.post(url, data=data, headers=merged_headers)
    else:
        raise Exception("Only POST, GET methods are supported")
    if rsp.status_code >= 400:
        raise Exception(rsp.status_code, rsp.text)

    if rsp_format == "text":
        return rsp.text

    return rsp.json()


def fetch_plots_info(program_text, realm, token):
    endpoint = "v2/signalflow/_/getPlotsInfo"
    response = make_request(endpoint,
                            method='POST',
                            data=program_text,
                            token=token,
                            realm=realm)
    return response


def fetch_detector_sf_model(program_text, realm, token):
    endpoint = "v2/signalflow/_/getSignalFlowModel?parseDetectors=true"
    result = make_request(endpoint,
                          method='POST',
                          data=program_text,
                          token=token,
                          realm=realm)
    return result


def fetch_detectors(name, realm, token):
    endpoint = f"v2/detector?name={name}&limit=10000"
    response = make_request(endpoint, token=token, realm=realm)
    detectors_list = response.get("results", [])
    return detectors_list


def fetch_detector_export_by_id(detector_id, realm, token):
    url = f"v2/detector/{detector_id}/export"
    data = make_request(url, token=token, realm=realm)
    return data


def fetch_detector_by_id(detector_id, realm, token):
    endpoint = f"v2/detector/{detector_id}"
    detector = make_request(endpoint, token=token, realm=realm)
    return detector


def create_new_detector(detector, realm, token):
    endpoint = "v2/detector"
    headers = {"Content-Type": "application/json"}
    created_detector = make_request(endpoint, method="POST", headers=headers,
                                    data=json.dumps(detector), token=token, realm=realm)
    return created_detector


def post_detector_validate(detector, realm, token):
    endpoint = "v2/detector/validate"
    headers = {"Content-Type": "application/json"}
    make_request(endpoint, method="POST", headers=headers,
                 data=json.dumps(detector), token=token, realm=realm, rsp_format='text')


def extract_import_qualifiers_from_detector_program_text(detector: object, realm: str, token: str):
    program_text = detector.get(DetectorScheme.PROGRAM_TEXT)
    program_text_metrics = fetch_plots_info(program_text, realm, token)
    metrics = []
    for metric_item in program_text_metrics:
        filters = metric_item.get("filters")
        for metric_filter in filters:
            metric_filter["property"] = metric_filter.get("name")
            del metric_filter["name"]
            metric_filter["not"] = False
            # In case of filter values ["*"] we need to update it to [] Reference thread:
            # https://splunk.slack.com/archives/CSN0BDJSJ/p1677149391265949?thread_ts=1677075481.884909&cid=CSN0BDJSJ
            if metric_filter["values"][0] == "*":
                metric_filter["values"] = []
        appended_metrics = [item.get("metric") for item in metrics]
        metric_name = metric_item.get("metricName")
        if metric_name not in appended_metrics:
            metrics.append({
                "metric": metric_name,
                "filters": filters,
            })
    return metrics


VALIDATORS_LIST = []


def init_detector_validators(validators_list):

    def wrap(func):
        def wrapped_validator(**kwargs):
            return func(**kwargs, validators_list=validators_list)
        return wrapped_validator

    return wrap


@init_detector_validators(validators_list=VALIDATORS_LIST)
def detector_validator(**kwargs):

    def add_validator(validator_func):
        validators_list = kwargs["validators_list"]
        desc = kwargs.get("desc")

        if desc is None:
            desc = validator_func.__name__
        fail_desc = kwargs.get("fail_desc", desc)

        def validator_wrapper(*args, **kwargs):
            passed = validator_func(*args, **kwargs)
            if type(passed) is not bool:
                raise RuntimeError("Detector validator should return boolean")

            if passed is True:
                return ValidationState.pass_validation(desc)
            else:
                return ValidationState.fail_validation(fail_desc)

        if validators_list is not None:
            validators_list.append(validator_wrapper)
        else:
            print("Incorrect use of decorator")
    return add_validator


@detector_validator(desc="SF model successfully extracted", fail_desc="Call to extract SF model API failed")
def validate_detector_sf_model(detector, **kwargs) -> bool:
    realm = kwargs.get("realm")
    token = kwargs.get("token")

    program_text = detector.get(DetectorScheme.PROGRAM_TEXT)

    try:
        fetch_detector_sf_model(program_text, realm, token)
    except Exception as e:
        print(e)
        return False

    return True


@detector_validator(desc="Detector has description")
def validate_description(detector, **kwargs) -> bool:

    detector_desc = detector.get("description", None)
    if detector_desc is None:
        return False

    return True


@detector_validator(desc="Autodetect supports one rule only")
def validate_num_of_rules(detector, **kwargs) -> bool:
    detector_rules = detector.get(DetectorScheme.RULES, [])
    if len(detector_rules) != 1:
        return False

    return True


@detector_validator(desc="Detector's dry run")
def validate_dry_run(detector, **kwargs) -> bool:
    realm = kwargs.get("realm")
    token = kwargs.get("token")
    try:
        post_detector_validate(detector, realm, token)
    except Exception as e:
        print(e)
        return False

    return True


def validate_detector(detector, validators_list, token, realm):
    is_detector_valid = True
    validation_results = []

    for validator in validators_list:
        result = validator(detector, token=token, realm=realm)
        if not result.passed:
            is_detector_valid = False
        validation_results.append(result)

    return is_detector_valid, validation_results


def get_git_branch(repo_location):
    """Checks whether working directory (of .blend file) contains a git repository.
    Returns branch if repository is found.
    """
    try:
        output = str(
            subprocess.check_output(
                ['git', 'branch'], cwd=repo_location, universal_newlines=True
            )
        )
        branch = [a for a in output.split('\n') if a.find('*') >= 0][0]
        return branch[branch.find('*') + 2:]
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        print("No git repository found.", "ERROR")
        return None


def read_detectors_from_local_path(path):
    data = {}
    for root, _, files in os.walk(path):
        for filename in files:
            if filename.endswith(".json"):
                with open(os.path.join(root, filename), 'r') as file:
                    existing_detector_export = json.loads(file.read())
                    import_qualifiers = existing_detector_export.get(DetectorExportScheme.DETECTOR_EXPORT) \
                        .get(DetectorExportScheme.DETECTOR) \
                        .get(DetectorScheme.IMPORT_QUALIFIERS)
                    data[existing_detector_export.get(DetectorScheme.ID)] = {
                        "filename": filename,
                        "id": existing_detector_export.get(DetectorScheme.ID),
                        "hashCode": existing_detector_export.get(DetectorExportScheme.HASH_CODE),
                        "importQualifiers": import_qualifiers,
                    }
    # print(data)
    return data


def write_to_file(path, content):
    with open(path, 'w') as file:
        file.write(content+'\n')


def generate_export_filename(detector):
    name = detector.get(DetectorScheme.NAME).replace('/', ' ').replace('>', 'over').replace('%', ' percent') \
        .replace('[', '').replace(']', '')
    return f"{name}.json"


def export_detector_to_file(detector, detector_export_props, realm, token, repo_location, skip_write=False):
    if detector.get(DetectorScheme.DETECTOR_ORIGIN) == ORIGIN_AUTODETECT:
        return DetectorExportInfo.skip_autodetect(detector)

    detector_export = fetch_detector_export_by_id(detector.get(DetectorScheme.ID), realm=realm, token=token)

    detector_hash_code = detector_export.get(DetectorExportScheme.HASH_CODE)
    detector = detector_export.get(DetectorExportScheme.DETECTOR_EXPORT).get(DetectorExportScheme.DETECTOR)

    if detector_hash_code == detector_export_props.get(DetectorExportScheme.HASH_CODE):
        return DetectorExportInfo.skip_no_changes(detector)

    valid, validation_results = validate_detector(detector, VALIDATORS_LIST, realm=realm, token=token)
    detector_state = detector_export_props.get("detector_state")

    if not valid:
        return DetectorExportInfo.skip_validation_errors(detector, detector_state, validation_results)

    for rule in detector.get(DetectorScheme.RULES, []):
        if rule[DetectorScheme.TIP] == "":
            rule[DetectorScheme.TIP] = None

        if rule[DetectorScheme.RUNBOOK_URL] == "":
            rule[DetectorScheme.RUNBOOK_URL] = None

    detector[DetectorScheme.IMPORT_QUALIFIERS] = detector_export_props.get(DetectorScheme.IMPORT_QUALIFIERS)
    detector[DetectorScheme.PACKAGE_SPECIFICATION] = ""

    detector_export.get(DetectorExportScheme.DETECTOR_EXPORT)[DetectorExportScheme.DETECTOR] = detector

    export_path = os.path.join(repo_location, "detector", detector_export_props.get("filename"))

    if not skip_write:
        write_to_file(export_path, json.dumps(detector_export, indent=2))

    return DetectorExportInfo.valid_export(detector, detector_state, validation_results, export_path)


def extract_detector_export_props(detector, existing_detectors_props, realm, token):
    detector_id = detector.get(DetectorScheme.ID)
    detector_settings = existing_detectors_props.get(detector_id, None)
    if detector_settings is None:
        detector_state = DetectorExportState.ADD_NEW
        new_qualifiers = extract_import_qualifiers_from_detector_program_text(detector, realm=realm, token=token)
        filename = generate_export_filename(detector)
        detector_settings = {
            "filename": filename,
            "hashCode": None,
            "importQualifiers": new_qualifiers,
        }
    else:
        detector_state = DetectorExportState.UPDATE_EXISTING
    return {**detector_settings, "detector_state": detector_state}


def get_detectors_list_to_export(realm, token, detector_id=None, detector_name='*'):
    if detector_id is not None:
        detector = fetch_detector_by_id(detector_id, token=token, realm=realm)
        detectors_list = [detector]
    else:
        name_pattern = "*" if detector_name is None else detector_name
        detectors_list = fetch_detectors(name_pattern, token=token, realm=realm)
    return detectors_list


def export_detectors(args):
    detectors_list = get_detectors_list_to_export(args.realm,
                                                  args.access_token,
                                                  detector_id=args.detector_id,
                                                  detector_name=args.detector_name)
    detector_path = os.sep.join([args.repo_location, "detector"])
    existing_detectors_props = read_detectors_from_local_path(detector_path)
    summary = []
    for detector in detectors_list:
        detector_export_props = extract_detector_export_props(detector,
                                                              existing_detectors_props,
                                                              token=args.access_token,
                                                              realm=args.realm)
        export_info = export_detector_to_file(detector, detector_export_props, repo_location=args.repo_location,
                                              realm=args.realm, token=args.access_token, skip_write=args.skip_write)
        export_info.print()
        summary.append(export_info)

    DetectorExportInfo.print_summary(summary)

    if args.skip_write:
        print(f"{Colors.BOLD}{Colors.OKBLUE}[Info] Export plan requested. No detectors exported {Colors.ENDC}")

    branch = get_git_branch(args.repo_location)
    print(f"[GIT BRANCH]: {branch}")


def import_detectors(args):
    detector_id = args.detector_id
    detector = fetch_detector_by_id(detector_id, realm=args.src_realm, token=args.src_access_token)
    detector[DetectorScheme.ID] = None

    imported_detector = create_new_detector(detector, realm=args.realm, token=args.access_token)
    imported_detector_id = imported_detector[DetectorScheme.ID]
    print(f"{Colors.BOLD}{Colors.OKGREEN}[Info] Detector successfully imported {imported_detector_id} {Colors.ENDC}")
    return None


def parse_cli():
    parser = argparse.ArgumentParser(description="Autodetect Detectors tool")

    parser.add_argument(
        "--access-token",
        "-t",
        dest="access_token",
        default=get_token_from_file(),
        required=True,
        type=str,
        help="The SignalFx org/user access token for the Org in which the built-in content resides. If not provided, this will \
         read from the file .token in this script's directory.",
    )

    parser.add_argument(
        "--env",
        "-e",
        dest="realm",
        default="us0",
        type=str,
        help="The SignalFx environment/realm (e.g. us0, lab0)",
    )

    subparsers = parser.add_subparsers(
        help="Choose an action",
        dest="action"
    )

    export_parser = subparsers.add_parser("export",
                                          help="Show all of the detectors to be exported")
    export_parser.set_defaults(func=export_detectors)
    export_parser.add_argument("--local-repo", "-lr",
                               dest='repo_location',
                               default=SCRIPT_DIR.as_posix(),
                               type=str,
                               help="Local content repo location on the disc")
    export_parser.add_argument("--id",
                               '-i',
                               metavar="detector-id",
                               dest="detector_id",
                               type=str,
                               help="ID of the detector")
    export_parser.add_argument("--name",
                               "-n",
                               metavar="detector-name",
                               dest="detector_name",
                               type=str,
                               help="Name pattern for the detector")

    export_subparser = export_parser.add_subparsers(dest="subaction",
                                                    required=True,
                                                    help="Choose export action: plan or apply")

    export_plan_parser = export_subparser.add_parser("plan",
                                                     help="Show all of the detectors to be exported")
    export_plan_parser.set_defaults(skip_write=True)

    export_apply_parser = export_subparser.add_parser("apply",
                                                      help="Show all of the detectors to be exported")
    export_apply_parser.set_defaults(skip_write=False)

    # Import detector arguments
    import_parser = subparsers.add_parser("import",
                                          help="Show all of the detectors to be exported")
    import_parser.set_defaults(func=import_detectors)
    import_parser.add_argument("--id",
                               '-i',
                               metavar="detector-id",
                               dest="detector_id",
                               type=str,
                               help="ID of the detector",
                               required=True)
    import_parser.add_argument("--src-env",
                               '-se',
                               dest="src_realm",
                               type=str,
                               required=True,
                               help="Env where imported detector resides")
    import_parser.add_argument("--src-access-token", "-st",
                               dest="src_access_token",
                               required=True,
                               type=str,
                               help="The SignalFx org/user access token where imported detector resides",
                               )

    args = parser.parse_args()

    if not args.action:
        print("ERROR: action is required")
        parser.print_help()
        return
    print('-' * 100)
    args.func(args)


if __name__ == '__main__':
    parse_cli()

