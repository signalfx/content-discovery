import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "content_changelog.py"
SPEC = importlib.util.spec_from_file_location("content_changelog", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ContentChangelogUnitTests(unittest.TestCase):
    def test_next_patch_version_uses_semantic_order(self):
        self.assertEqual(MODULE.next_patch_version(["2.9.9", "2.10.0"]), "2.10.1")

    def test_next_patch_version_uses_metadata_baseline_when_history_is_empty(self):
        self.assertEqual(MODULE.next_patch_version([], "2.0.0"), "2.0.1")

    def test_changed_paths_includes_both_sides_of_rename(self):
        change = MODULE.ContentChange("R", "detector/New.json", "detector/Old.json")
        self.assertEqual(
            MODULE.changed_paths([change]),
            {"detector/New.json", "detector/Old.json"},
        )

    def test_navigator_description_reports_exact_display_name_change(self):
        change = MODULE.ContentChange("M", "navigators/Apache/server.json")
        old = {
            "navigatorExport": {
                "navigator": {
                    "uiModel": {"displayName": "Apache Server CPU utilization"}
                }
            },
            "hashCode": 1,
        }
        new = {
            "navigatorExport": {
                "navigator": {
                    "uiModel": {"displayName": "Apache server CPU utilization"}
                }
            },
            "hashCode": 2,
        }
        with mock.patch.object(MODULE, "previous_change_document", return_value=old), mock.patch.object(
            MODULE, "read_change_document", return_value=new
        ):
            description = MODULE.describe_modified_content(
                change, "Apache web servers", "navigator"
            )

        self.assertEqual(
            description,
            'Changed display name from "Apache Server CPU utilization" to "Apache server CPU utilization".',
        )

    def test_dashboard_group_description_counts_changed_chart_programs(self):
        change = MODULE.ContentChange("M", "group/AWS Redshift.json")
        old = {
            "chartExports": [
                {"chart": {"id": "one", "programText": "old one"}},
                {"chart": {"id": "two", "programText": "old two"}},
            ],
            "hashCode": 1,
        }
        new = {
            "chartExports": [
                {"chart": {"id": "one", "programText": "new one"}},
                {"chart": {"id": "two", "programText": "new two"}},
            ],
            "hashCode": 2,
        }
        with mock.patch.object(MODULE, "previous_change_document", return_value=old), mock.patch.object(
            MODULE, "read_change_document", return_value=new
        ):
            description = MODULE.describe_modified_content(
                change, "AWS Redshift", "dashboard_group"
            )

        self.assertEqual(description, "Updated program text in 2 charts.")


class ContentChangelogIntegrationTests(unittest.TestCase):
    def run_git(self, root, *args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True
        )

    def test_update_is_idempotent_and_adds_one_entry_per_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_git(root, "init")
            self.run_git(root, "config", "user.email", "test@example.com")
            self.run_git(root, "config", "user.name", "Test User")
            self.run_git(root, "config", "commit.gpgsign", "false")
            (root / "detector").mkdir()
            (root / "navigators").mkdir()
            (root / "content_release_notes.yaml").write_text(
                "metadata: {version: 2.0.0}\nversions: {}\n", encoding="utf-8"
            )
            (root / "detector" / "CPU.json").write_text(
                '{"detectorExport":{"detector":{"name":"CPU"}}}', encoding="utf-8"
            )
            self.run_git(root, "add", ".")
            self.run_git(root, "commit", "-m", "initial")
            (root / "detector" / "CPU.json").write_text(
                '{"detectorExport":{"detector":{"name":"CPU usage"}}}', encoding="utf-8"
            )
            (root / "navigators" / "Hosts.json").write_text(
                '{"navigatorExport":{"navigator":{"name":"Hosts"}}}', encoding="utf-8"
            )
            self.run_git(root, "add", "detector/CPU.json", "navigators/Hosts.json")

            with mock.patch.object(MODULE, "REPO_ROOT", root), mock.patch.object(
                MODULE, "CHANGELOG_PATH", root / "content_release_notes.yaml"
            ):
                self.assertTrue(MODULE.update_staged(stage_output=True))
                first = (root / "content_release_notes.yaml").read_text(encoding="utf-8")
                self.assertFalse(MODULE.update_staged(stage_output=True))
                self.assertEqual(
                    first,
                    (root / "content_release_notes.yaml").read_text(encoding="utf-8"),
                )
                self.assertTrue(MODULE.validate_staged())

            data = yaml.safe_load(first)
            self.assertEqual(next(iter(data["versions"])), "2.0.1")
            entry = next(iter(data["versions"].values()))
            self.assertEqual(len(entry["files"]), 2)
            detector_entry = next(
                item for item in entry["files"] if item["category"] == "detector"
            )
            self.assertEqual(
                detector_entry["description"],
                'Changed name from "CPU" to "CPU usage".',
            )

    def test_base_validation_rejects_only_historical_file_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_git(root, "init")
            self.run_git(root, "config", "user.email", "test@example.com")
            self.run_git(root, "config", "user.name", "Test User")
            self.run_git(root, "config", "commit.gpgsign", "false")
            (root / "detector").mkdir()
            (root / "detector" / "CPU.json").write_text(
                '{"detectorExport":{"detector":{"name":"CPU"}},"value":1}',
                encoding="utf-8",
            )
            (root / "content_release_notes.yaml").write_text(
                """metadata: {version: 2.0.0}
versions:
  1.0.0:
    files:
      - name: CPU
        category: detector
        files_modified: [detector/CPU.json]
""",
                encoding="utf-8",
            )
            self.run_git(root, "add", ".")
            self.run_git(root, "commit", "-m", "initial")
            base = self.run_git(root, "rev-parse", "HEAD").stdout.strip()
            (root / "detector" / "CPU.json").write_text(
                '{"detectorExport":{"detector":{"name":"CPU"}},"value":2}',
                encoding="utf-8",
            )
            self.run_git(root, "add", "detector/CPU.json")
            self.run_git(root, "commit", "-m", "undocumented update")

            with mock.patch.object(MODULE, "REPO_ROOT", root), mock.patch.object(
                MODULE, "CHANGELOG_PATH", root / "content_release_notes.yaml"
            ):
                self.assertFalse(MODULE.validate_base(base))

    def test_staged_validation_parses_changelog_without_content_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.run_git(root, "init")
            (root / "content_release_notes.yaml").write_text("versions: [", encoding="utf-8")
            self.run_git(root, "add", "content_release_notes.yaml")

            with mock.patch.object(MODULE, "REPO_ROOT", root), mock.patch.object(
                MODULE, "CHANGELOG_PATH", root / "content_release_notes.yaml"
            ):
                with self.assertRaises(RuntimeError):
                    MODULE.validate_staged()


if __name__ == "__main__":
    unittest.main()
