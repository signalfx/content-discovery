#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List
from urllib.parse import quote

import requests

SCRIPT_DIR = Path(__file__).parent

SYSTEM_USER_ID = "AAAAAAAAAAA"


def do_get(url, token):
    return requests.get(url, headers={"X-SF-TOKEN": token})


def fetch_export_by_id(group_id, base_url, token, format="json"):
    resp = do_get(f"{base_url}/v2/dashboardgroup/{group_id}/export", token)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch dashboard group {group_id}: {resp.text}")
    if format == "json":
        return resp.json()
    return resp.text


def fetch_all_dashboard_groups(base_url, token):
    resp = do_get(f"{base_url}/v2/dashboardgroup?limit=1000", token)
    return resp.json().get("results")


def fetch_dashboard_group_by_name(group_name, base_url, token):
    resp = do_get(f"{base_url}/v2/dashboardgroup?name={quote(group_name.encode('utf-8'))}", token).json()

    for group in resp["results"]:
        if group.get("creator") == SYSTEM_USER_ID:
            # We don't want the imported built-in content, only the custom ones
            # that are used in this repo.
            continue
        if group.get("name").lower() == group_name.lower():
            return group
    return None


def get_token_from_file() -> str:
    try:
        token = (SCRIPT_DIR / ".token").read_text()
    except OSError:
        return None

    return token.strip()


DATA_RE = re.compile(r"""data\(['"]([^'"]+)['"]""")


def all_metrics_from_charts(group_export) -> List[str]:
    programs = [c["chart"]["programText"] for c in group_export["chartExports"]]
    return sorted(set([g for p in programs for g in DATA_RE.findall(p)]))


def metrics_command(args, base_url, token):
    group = fetch_dashboard_group_by_name(args.group_name[0], base_url, token)
    if group is None:
        print(f"Could not find built-in dashboard group '{args.group_name[0]}'", file=sys.stderr)
        return

    exported_group = fetch_export_by_id(group["id"], base_url, token)
    for metric in all_metrics_from_charts(exported_group):
        print(metric)


def export_command(args, base_url, token):
    group_id = args.group_id[0]
    print(fetch_export_by_id(group_id, base_url, token, format="text"))


def reexport_command(args, base_url, token):
    group_id = json.loads(Path(args.group_file[0]).read_bytes())["groupExport"]["group"]["id"]
    print(fetch_export_by_id(group_id, base_url, token, format="text"))


def parse_cli():
    parser = argparse.ArgumentParser(description="Built-in Dashboard Group Swiss Army Knife")

    parser.add_argument(
        "--access-token",
        "-t",
        dest="access_token",
        type=str,
        default=get_token_from_file(),
        help="The SignalFx org/user access token for the org in which the content resides. If not provided, this will read from the file .token in this script's directory.",
    )

    parser.add_argument("--env", "-e", type=str, default="us0", help="The SignalFx environment/realm (e.g. us0, lab0)")

    subparsers = parser.add_subparsers(help="What to do with the dashboard group", dest="subcommand")

    metrics_parser = subparsers.add_parser("metrics", help="Show all of the metrics used in a dashboard group")
    metrics_parser.add_argument(
        "group_name", metavar="group-name", type=str, nargs=1, help="The name of the dashboard group"
    )
    metrics_parser.set_defaults(func=metrics_command)

    export_parser = subparsers.add_parser("export", help="Export a dashboard group")
    export_parser.add_argument("group_id", metavar="group-id", nargs=1, type=str, help="The id of the dashboard group")
    export_parser.set_defaults(func=export_command)

    reexport_parser = subparsers.add_parser(
        "reexport", help="Export a dashboard group based on an existing group export file"
    )
    reexport_parser.add_argument(
        "group_file", metavar="group-file", nargs=1, type=str, help="Path to an already exported dashboard group"
    )
    reexport_parser.set_defaults(func=reexport_command)

    args = parser.parse_args()

    if not args.subcommand:
        print("ERROR: subcommand is required")
        parser.print_help()
        return

    base_api_url = base_api_url_from_env(args.env)

    args.func(args, base_url=base_api_url, token=args.access_token)


def base_api_url_from_env(env: str) -> str:
    if env == "lab0":
        return "http://lab.corp.signalfx.com"
    return f"https://api.{env}.signalfx.com"


if __name__ == "__main__":
    parse_cli()
