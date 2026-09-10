#!/usr/bin/env python3
"""Deterministic CLI for SignalFx content object APIs."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
TOKEN_FILE = REPO_ROOT / ".token"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sfx_client import (  # noqa: E402
    create_object,
    export_object,
    get_object,
    prepare_payload,
    update_object,
)


OPERATIONS = ("get", "export", "create", "update")
MASTER_REALM = "us0"
MASTER_API_HOSTS = {
    "api.us0.observability.splunkcloud.com",
    "api.us0.signalfx.com",
}
RESOURCE_ALIASES = {
    "navigator": "navigator",
    "detector": "detector",
    "datalink": "datalink",
    "crosslink": "datalink",
    "dashboard-group": "dashboard-group",
    "group": "dashboard-group",
    "chart": "chart",
    "dashboard": "dashboard",
}

PAYLOAD_PATHS = {
    "navigator": (("navigatorExport", "navigator"), ("navigator",)),
    "detector": (("detectorExport", "detector"), ("detector",)),
    "datalink": (("crosslink",), ("crossLink",)),
    "dashboard-group": (("groupExport", "group"), ("group",)),
    "chart": (("chart",),),
    "dashboard": (("dashboard",),),
}

class CliError(RuntimeError):
    """Expected command failure with a stable process exit code."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Get, export, create, or update SignalFx content objects."
    )
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("resource", choices=tuple(RESOURCE_ALIASES))
    parser.add_argument(
        "id",
        nargs="?",
        help="Remote object ID; required for get, export, and update",
    )
    parser.add_argument("--file", type=Path, help="JSON request or export payload")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the raw export JSON to this file; valid only with export",
    )
    parser.add_argument("--yes", action="store_true", help="Confirm a remote mutation")
    parser.add_argument(
        "--base-url",
        help="Approved Master SignalBuddy HTTPS API host, optionally ending in /v2",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    read_operation = args.operation in ("get", "export")

    if args.operation in ("get", "export", "update") and not args.id:
        raise CliError(f"{args.operation} requires a remote object ID")
    if args.operation == "create" and args.id:
        raise CliError("create does not accept a remote object ID")

    if args.operation in ("create", "update") and not args.file:
        raise CliError(f"{args.operation} requires --file")
    if args.operation not in ("create", "update") and args.file:
        raise CliError(f"{args.operation} does not accept --file")

    if read_operation and args.yes:
        raise CliError(f"{args.operation} does not accept --yes")
    if args.operation in ("create", "update") and not args.yes:
        raise CliError(f"{args.operation} changes remote content; pass --yes to confirm")

    if args.output and args.operation != "export":
        raise CliError("--output is valid only with export")


def resolve_token(environ: Mapping[str, str] = os.environ) -> str:
    for name in ("SFX_ACCESS_TOKEN", "SIGNALBUDDY_TOKEN"):
        token = environ.get(name, "").strip()
        if token:
            return token

    if TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token

    raise CliError(
        "SignalFx token not found; set SFX_ACCESS_TOKEN or SIGNALBUDDY_TOKEN, "
        "or create the repository .token file"
    )


def resolve_base_url(args: argparse.Namespace) -> str:
    if args.base_url:
        parsed = urlsplit(args.base_url)
        hostname = (parsed.hostname or "").lower()
        try:
            port = parsed.port
        except ValueError as exc:
            raise CliError(f"invalid --base-url: {exc}") from exc
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port not in (None, 443)
            or hostname not in MASTER_API_HOSTS
            or parsed.path.rstrip("/") not in ("", "/v2")
            or parsed.query
            or parsed.fragment
        ):
            raise CliError(
                "--base-url must be an approved Master SignalBuddy HTTPS API host "
                "without credentials, query parameters, or a path other than /v2"
            )
        return f"https://{hostname}"
    return f"https://api.{MASTER_REALM}.observability.splunkcloud.com"


def _nested_object(raw: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any] | None:
    value: Any = raw
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if not isinstance(value, dict):
        raise CliError(f"{'.'.join(path)} must contain a JSON object")
    return value


def load_payload(path: Path, resource: str, operation: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CliError(f"input file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CliError(f"input file is not valid JSON: {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise CliError("input JSON must be an object")

    payload = raw
    for candidate in PAYLOAD_PATHS[resource]:
        nested = _nested_object(raw, candidate)
        if nested is not None:
            payload = nested
            break

    if operation in ("create", "update"):
        return prepare_payload(payload)
    return dict(payload)


def invoke(args: argparse.Namespace, token: str, base_url: str) -> Any:
    resource = RESOURCE_ALIASES[args.resource]
    with contextlib.redirect_stdout(sys.stderr):
        if args.operation == "get":
            return get_object(resource, args.id, base_url, token)
        if args.operation == "export":
            return export_object(resource, args.id, base_url, token)
        payload = load_payload(args.file, resource, args.operation)
        if args.operation == "create":
            return create_object(resource, payload, base_url, token)
        return update_object(resource, args.id, payload, base_url, token)


def emit_result(args: argparse.Namespace, result: Any) -> None:
    if args.output:
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = {"output": str(args.output)}
    json.dump(
        {
            "ok": True,
            "operation": args.operation,
            "resource": RESOURCE_ALIASES[args.resource],
            "result": result,
        },
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        validate_args(args)
        result = invoke(args, resolve_token(), resolve_base_url(args))
        emit_result(args, result)
        return 0
    except CliError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stderr, sort_keys=True)
        sys.stderr.write("\n")
        return exc.exit_code
    except Exception as exc:  # Keep credentials and request headers out of output.
        json.dump({"ok": False, "error": str(exc)}, sys.stderr, sort_keys=True)
        sys.stderr.write("\n")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
