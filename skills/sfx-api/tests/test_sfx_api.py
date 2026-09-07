from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sfx_api


class SfxApiTest(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(sfx_api, "resolve_token", return_value="secret"),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = sfx_api.main(argv)
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def write_payload(self, payload: dict) -> Path:
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        with handle:
            json.dump(payload, handle)
        return Path(handle.name)

    def test_all_six_resources_expose_all_five_commands(self) -> None:
        self.assertEqual(
            set(sfx_api.RESOURCE_ALIASES.values()),
            {"navigator", "detector", "datalink", "dashboard-group", "chart", "dashboard"},
        )
        self.assertEqual(
            set(sfx_api.OPERATIONS), {"get", "export", "create", "update", "delete"}
        )

    def test_get_chart_dispatches_to_object_service(self) -> None:
        with mock.patch.object(sfx_api, "get_object", return_value={"id": "chart-1"}) as getter:
            exit_code, stdout, stderr = self.run_cli(
                ["get", "chart", "chart-1", "--realm", "eu0"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")
        getter.assert_called_once_with(
            "chart",
            "chart-1",
            "https://api.eu0.observability.splunkcloud.com",
            "secret",
        )
        self.assertEqual(json.loads(stdout)["result"], {"id": "chart-1"})

    def test_export_group_alias_writes_raw_export(self) -> None:
        output = self.write_payload({})
        export = {"groupExport": {"group": {"id": "group-1"}}}
        with mock.patch.object(sfx_api, "export_object", return_value=export) as exporter:
            exit_code, stdout, _ = self.run_cli(
                ["export", "group", "group-1", "--output", str(output)]
            )

        self.assertEqual(exit_code, 0)
        exporter.assert_called_once_with(
            "dashboard-group",
            "group-1",
            "https://api.us0.observability.splunkcloud.com",
            "secret",
        )
        self.assertEqual(json.loads(output.read_text()), export)
        self.assertEqual(json.loads(stdout)["result"], {"output": str(output)})

    def test_create_navigator_extracts_object_and_strips_server_fields(self) -> None:
        path = self.write_payload(
            {
                "navigatorExport": {
                    "navigator": {
                        "id": "old-id",
                        "created": 1,
                        "name": "Kubernetes",
                    }
                }
            }
        )
        with mock.patch.object(sfx_api, "create_object", return_value={"id": "new-id"}) as creator:
            exit_code, stdout, _ = self.run_cli(
                ["create", "navigator", "--file", str(path), "--yes"]
            )

        self.assertEqual(exit_code, 0)
        creator.assert_called_once_with(
            "navigator",
            {"name": "Kubernetes"},
            "https://api.us0.observability.splunkcloud.com",
            "secret",
        )
        self.assertEqual(json.loads(stdout)["result"], {"id": "new-id"})

    def test_update_datalink_uses_explicit_id(self) -> None:
        path = self.write_payload({"crossLink": {"id": "source-id", "propertyName": "service.name"}})
        with mock.patch.object(sfx_api, "update_object", return_value={"id": "target-id"}) as updater:
            exit_code, _, _ = self.run_cli(
                ["update", "crosslink", "target-id", "--file", str(path), "--yes"]
            )

        self.assertEqual(exit_code, 0)
        updater.assert_called_once_with(
            "datalink",
            "target-id",
            {"propertyName": "service.name"},
            "https://api.us0.observability.splunkcloud.com",
            "secret",
        )

    def test_delete_requires_confirmation(self) -> None:
        with mock.patch.object(sfx_api, "delete_object") as deleter:
            exit_code, stdout, stderr = self.run_cli(
                ["delete", "dashboard", "dashboard-1"]
            )

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("pass --yes to confirm", stderr)
        deleter.assert_not_called()

    def test_delete_dispatches_and_reports_empty_success(self) -> None:
        with mock.patch.object(sfx_api, "delete_object", return_value=None) as deleter:
            exit_code, stdout, _ = self.run_cli(
                ["delete", "detector", "detector-1", "--yes"]
            )

        self.assertEqual(exit_code, 0)
        deleter.assert_called_once()
        self.assertEqual(json.loads(stdout)["result"], {"deleted": "detector-1"})


if __name__ == "__main__":
    unittest.main()
