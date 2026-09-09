from __future__ import annotations

import argparse
import copy
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SFX_SCRIPT_DIR = Path(__file__).resolve().parents[2] / "sfx-api" / "scripts"
for import_dir in (SCRIPT_DIR, SFX_SCRIPT_DIR):
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

import datalink_sync
import group_sync
import sync_changed as cli
import sync_utils as utils


class SyncApplyTest(unittest.TestCase):
    def test_sync_skill_resolves_repository_root(self) -> None:
        expected = Path(__file__).resolve().parents[3]
        self.assertEqual(cli.REPO_ROOT, expected)

    def test_apply_updates_then_exports_to_same_file(self) -> None:
        path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        self.addCleanup(path.unlink, missing_ok=True)
        path.write_text("{}", encoding="utf-8")
        events: list[str] = []
        args = argparse.Namespace(yes=True, base="origin/master", paths=None)

        with (
            mock.patch.object(cli, "resolve_credentials", return_value=("us0", "token")),
            mock.patch.object(cli, "get_changed_files", return_value=[("navigator", path)]) as changed,
            mock.patch.object(cli, "extract_resource_info", return_value=("nav-1", "Navigator")),
            mock.patch.object(cli, "_load_local_json", return_value={"navigatorExport": {}}),
            mock.patch.object(
                cli,
                "_apply_resource",
                side_effect=lambda *_: events.append("update") or True,
            ),
            mock.patch.object(
                cli,
                "_refresh_local",
                side_effect=lambda *_, **__: events.append("export") or path,
            ),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            exit_code = cli.cmd_apply(args)

        self.assertEqual(exit_code, cli.EXIT_OK)
        changed.assert_called_once_with("origin/master")
        self.assertEqual(events, ["update", "export"])

    def test_failed_update_does_not_overwrite_local_file(self) -> None:
        path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        self.addCleanup(path.unlink, missing_ok=True)
        args = argparse.Namespace(yes=True, base=None, paths=None)

        with (
            mock.patch.object(cli, "resolve_credentials", return_value=("us0", "token")),
            mock.patch.object(cli, "get_changed_files", return_value=[("detector", path)]),
            mock.patch.object(cli, "extract_resource_info", return_value=("det-1", "Detector")),
            mock.patch.object(cli, "_load_local_json", return_value={"detectorExport": {}}),
            mock.patch.object(cli, "_apply_resource", return_value=False),
            mock.patch.object(cli, "_refresh_local") as refresh,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = cli.cmd_apply(args)

        self.assertEqual(exit_code, cli.EXIT_PARTIAL)
        refresh.assert_not_called()


class ChangeDetectionTest(unittest.TestCase):
    def test_feature_branch_changes_are_compared_from_merge_base(self) -> None:
        navigator = next((utils.REPO_ROOT / "navigators").rglob("*.json"))
        relative = str(navigator.relative_to(utils.REPO_ROOT))

        def git_lines(args):
            if args[0] == "merge-base":
                return ["base-sha"]
            if args[0] == "diff":
                self.assertEqual(args[2], "base-sha")
                return [relative]
            if args[0] == "ls-files":
                return []
            raise AssertionError(f"unexpected git arguments: {args}")

        with (
            mock.patch.object(utils, "_default_change_base", return_value="origin/master"),
            mock.patch.object(utils, "_git_lines", side_effect=git_lines),
        ):
            changed = utils.get_changed_files()

        self.assertEqual(changed, [("navigator", navigator)])


class FormatPreservingWriteTest(unittest.TestCase):
    def test_group_write_changes_values_without_reformatting_existing_json(self) -> None:
        path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        self.addCleanup(path.unlink, missing_ok=True)
        original = """{
  \"chartExports\" : [ {
    \"chart\" : {
      \"id\" : \"chart-1\",
      \"programText\" : \"old program\",
      \"tags\" : null
    }
  } ],
  \"hashCode\" : 1
}
"""
        path.write_text(original, encoding="utf-8")
        fresh = {
            "chartExports": [
                {
                    "chart": {
                        "id": "chart-1",
                        "programText": "new program",
                        "tags": [],
                    }
                }
            ],
            "hashCode": 2,
        }

        utils.write_local_resource(path, fresh, preserve_format=True)

        expected = original.replace("old program", "new program").replace(
            '"hashCode" : 1', '"hashCode" : 2'
        )
        self.assertEqual(path.read_text(encoding="utf-8"), expected)
        self.assertIn('"tags" : null', path.read_text(encoding="utf-8"))

    def test_group_write_refuses_unmappable_root_instead_of_reformatting(self) -> None:
        path = Path(tempfile.NamedTemporaryFile(suffix=".json", delete=False).name)
        self.addCleanup(path.unlink, missing_ok=True)
        original = '{\n  "hashCode" : 1\n}\n'
        path.write_text(original, encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "cannot safely preserve"):
            utils.write_local_resource(
                path,
                {"hashCode": 2, "chartExports": []},
                preserve_format=True,
            )

        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_export_comparison_ignores_null_empty_collection_normalization(self) -> None:
        local = {
            "tags": None,
            "filters": {"sources": None, "variables": None},
        }
        remote = {
            "tags": [],
            "filters": {"sources": [], "variables": []},
        }

        self.assertTrue(utils.export_values_equal(local, remote))
        self.assertFalse(group_sync._has_chart_changed(local, remote))
        self.assertFalse(group_sync._has_dashboard_changed(local, remote))
        summary = utils.summarize_group_changes(
            {"groupExport": {"group": {"teams": None}}},
            {"groupExport": {"group": {"teams": []}}},
        )
        self.assertFalse(summary["group_modified"])

    def test_export_comparison_still_detects_meaningful_change(self) -> None:
        local = {"programText": "A = data('metric').mean()", "tags": None}
        remote = {"programText": "A = data('metric').sum()", "tags": []}

        self.assertFalse(utils.export_values_equal(local, remote))
        self.assertTrue(group_sync._has_chart_changed(local, remote))

    def test_three_way_writeback_keeps_unrelated_remote_drift_out(self) -> None:
        baseline = {
            "chartExports": [
                {"chart": {"id": "chart-1", "programText": "old", "tags": None}},
                {"chart": {"id": "chart-2", "programText": "unchanged"}},
            ],
            "hashCode": 1,
        }
        local = {
            "chartExports": [
                {"chart": {"id": "chart-1", "programText": "new", "tags": None}},
                {"chart": {"id": "chart-2", "programText": "unchanged"}},
            ],
            "hashCode": 2,
        }
        fresh = {
            "chartExports": [
                {"chart": {"id": "chart-2", "programText": "remote drift"}},
                {"chart": {"id": "chart-1", "programText": "new", "tags": []}},
            ],
            "hashCode": 3,
        }

        merged = cli._merge_changed_export_values(baseline, local, fresh)

        self.assertEqual(merged["chartExports"][0]["chart"]["programText"], "new")
        self.assertIsNone(merged["chartExports"][0]["chart"]["tags"])
        self.assertEqual(
            merged["chartExports"][1]["chart"]["programText"], "unchanged"
        )
        self.assertEqual(merged["hashCode"], 3)


class GroupOrderTest(unittest.TestCase):
    def test_group_progress_is_written_to_stderr(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        local = {"chart-1": {"id": "chart-1", "name": "New chart"}}

        with (
            mock.patch.object(
                group_sync, "create_object", return_value={"id": "new-chart-1"}
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            replacements = group_sync._sync_children(
                "chart", local, {}, {}, "https://api", "token"
            )

        self.assertEqual(replacements, {"chart-1": "new-chart-1"})
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Created chart: New chart", stderr.getvalue())

    def test_group_updates_in_dependency_order(self) -> None:
        remote = {
            "chartExports": [{"chart": {"id": "chart-1", "name": "Old chart"}}],
            "dashboardExports": [
                {"dashboard": {"id": "dash-1", "name": "Old dashboard", "charts": []}}
            ],
            "groupExport": {
                "group": {
                    "id": "group-1",
                    "name": "Old group",
                    "dashboards": ["dash-1"],
                }
            },
            "crossLinkExports": [],
        }
        local = {
            "chartExports": [{"chart": {"id": "chart-1", "name": "New chart"}}],
            "dashboardExports": [
                {"dashboard": {"id": "dash-1", "name": "New dashboard", "charts": []}}
            ],
            "groupExport": {
                "group": {
                    "id": "group-1",
                    "name": "New group",
                    "dashboards": ["dash-1"],
                }
            },
            "crossLinkExports": [{"crosslink": {"id": "link-1"}}],
        }
        order: list[str] = []

        def record_update(resource, *_args):
            order.append(resource)
            return {"id": _args[0]}

        with (
            mock.patch.object(group_sync, "fetch_group_export_by_id", return_value=remote),
            mock.patch.object(group_sync, "update_object", side_effect=record_update),
            mock.patch.object(
                group_sync,
                "update_crosslinks",
                side_effect=lambda *_: order.append("datalink") or (1, 0, 0),
            ),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = group_sync.update_dashboard_group(local, "https://api", "token")

        self.assertTrue(result)
        self.assertEqual(order, ["chart", "dashboard", "dashboard-group", "datalink"])

    def test_new_chart_id_is_remapped_before_dashboard_create(self) -> None:
        remote = {
            "chartExports": [],
            "dashboardExports": [],
            "groupExport": {"group": {"id": "group-1", "name": "Group", "dashboards": []}},
            "crossLinkExports": [],
        }
        local = {
            "chartExports": [{"chart": {"id": "old-chart", "name": "Chart"}}],
            "dashboardExports": [
                {
                    "dashboard": {
                        "id": "old-dashboard",
                        "name": "Dashboard",
                        "charts": [{"chartId": "old-chart"}],
                    }
                }
            ],
            "groupExport": {
                "group": {
                    "id": "group-1",
                    "name": "Group",
                    "dashboards": ["old-dashboard"],
                }
            },
            "crossLinkExports": [],
        }
        created_payloads: dict[str, dict] = {}

        def create(resource, payload, *_args):
            created_payloads[resource] = payload
            return {"id": f"new-{resource}"}

        with (
            mock.patch.object(group_sync, "fetch_group_export_by_id", return_value=remote),
            mock.patch.object(group_sync, "create_object", side_effect=create),
            mock.patch.object(group_sync, "update_object", return_value={}),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = group_sync.update_dashboard_group(local, "https://api", "token")

        self.assertTrue(result)
        self.assertEqual(
            created_payloads["dashboard"]["charts"][0]["chartId"], "new-chart"
        )

    def test_group_update_only_writes_children_changed_from_baseline(self) -> None:
        baseline = {
            "chartExports": [
                {"chart": {"id": "chart-1", "programText": "old"}},
                {"chart": {"id": "chart-2", "programText": "same"}},
            ],
            "dashboardExports": [
                {"dashboard": {"id": "dash-1", "name": "Dashboard"}}
            ],
            "groupExport": {"group": {"id": "group-1", "name": "Group"}},
            "crossLinkExports": [],
        }
        local = copy.deepcopy(baseline)
        local["chartExports"][0]["chart"]["programText"] = "new"
        remote = copy.deepcopy(baseline)
        remote["chartExports"][1]["chart"]["programText"] = "remote drift"
        remote["dashboardExports"][0]["dashboard"]["locked"] = False
        updates: list[tuple[str, str]] = []

        def update(resource, object_id, *_args):
            updates.append((resource, object_id))
            return {"id": object_id}

        with (
            mock.patch.object(group_sync, "fetch_group_export_by_id", return_value=remote),
            mock.patch.object(group_sync, "update_object", side_effect=update),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = group_sync.update_dashboard_group(
                local, "https://api", "token", baseline
            )

        self.assertTrue(result)
        self.assertEqual(updates, [("chart", "chart-1")])


class CrosslinkOutputTest(unittest.TestCase):
    def test_crosslink_progress_is_written_to_stderr(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        exports = [{"crosslink": {"propertyName": "host.name"}}]

        with (
            mock.patch.object(datalink_sync, "update_crosslink", return_value=True),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = datalink_sync.update_crosslinks(
                exports, "https://api", "token"
            )

        self.assertEqual(result, (0, 1, 0))
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Created crosslink: host.name", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
