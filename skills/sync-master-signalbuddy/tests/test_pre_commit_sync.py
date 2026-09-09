from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pre_commit_sync as hook


def completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class PreCommitSyncTest(unittest.TestCase):
    def test_only_supported_staged_json_is_selected(self) -> None:
        with mock.patch.object(
            hook,
            "_git_paths",
            return_value=[
                "README.md",
                "navigators/AWS/Instances.json",
                "detector/CPU.json",
                "group/Kubernetes.json",
                "group/notes.txt",
            ],
        ):
            self.assertEqual(
                hook.staged_content_paths(),
                [
                    "detector/CPU.json",
                    "group/Kubernetes.json",
                    "navigators/AWS/Instances.json",
                ],
            )

    def test_unrelated_commit_only_runs_validation(self) -> None:
        with (
            mock.patch.object(hook, "staged_content_paths", return_value=[]),
            mock.patch.object(hook, "validate_content") as validate,
            mock.patch.object(hook, "run_sync_command") as sync,
        ):
            self.assertEqual(hook.main(), 0)

        validate.assert_called_once_with()
        sync.assert_not_called()

    def test_mixed_staged_and_unstaged_content_is_blocked(self) -> None:
        paths = ["detector/CPU.json"]
        with (
            mock.patch.object(hook, "staged_content_paths", return_value=paths),
            mock.patch.object(hook, "validate_content"),
            mock.patch.object(hook, "unstaged_versions", return_value=paths),
            mock.patch.object(hook, "run_sync_command") as sync,
        ):
            self.assertEqual(hook.main(), 1)

        sync.assert_not_called()

    def test_success_plans_applies_restages_and_revalidates(self) -> None:
        paths = ["group/Kubernetes.json"]
        with (
            mock.patch.object(hook, "staged_content_paths", return_value=paths),
            mock.patch.object(hook, "unstaged_versions", return_value=[]),
            mock.patch.object(hook, "validate_content") as validate,
            mock.patch.object(
                hook,
                "run_sync_command",
                side_effect=[
                    {
                        "command": "plan",
                        "fetch_errors": 0,
                        "resources": [{"path": "group/Kubernetes.json"}],
                    },
                    {
                        "command": "apply",
                        "failed_count": 0,
                        "results": [
                            {"path": "group/Kubernetes.json", "status": "applied"}
                        ],
                    },
                ],
            ) as sync,
            mock.patch.object(hook, "_run", return_value=completed()) as run,
        ):
            self.assertEqual(hook.main(), 0)

        validate.assert_called_once_with()
        self.assertEqual(
            sync.call_args_list,
            [mock.call("plan", paths), mock.call("apply", paths)],
        )
        run.assert_called_once_with(
            ("git", "add", "--", "group/Kubernetes.json"), capture_output=True
        )

    def test_content_validation_runs_only_after_sync_and_restage(self) -> None:
        paths = ["navigators/Apache/apacheserverotel.json"]
        events: list[str] = []

        def sync(command: str, _paths: list[str]) -> dict[str, object]:
            events.append(command)
            if command == "plan":
                return {
                    "fetch_errors": 0,
                    "resources": [{"path": paths[0]}],
                }
            return {
                "failed_count": 0,
                "results": [{"path": paths[0], "status": "applied"}],
            }

        with (
            mock.patch.object(hook, "staged_content_paths", return_value=paths),
            mock.patch.object(hook, "unstaged_versions", return_value=[]),
            mock.patch.object(hook, "run_sync_command", side_effect=sync),
            mock.patch.object(
                hook,
                "_run",
                side_effect=lambda *_args, **_kwargs: events.append("restage")
                or completed(),
            ),
            mock.patch.object(
                hook,
                "validate_content",
                side_effect=lambda: events.append("validate"),
            ),
        ):
            self.assertEqual(hook.main(), 0)

        self.assertEqual(events, ["plan", "apply", "restage", "validate"])

    def test_fetch_error_blocks_apply(self) -> None:
        paths = ["detector/CPU.json"]
        with (
            mock.patch.object(hook, "staged_content_paths", return_value=paths),
            mock.patch.object(hook, "unstaged_versions", return_value=[]),
            mock.patch.object(hook, "validate_content"),
            mock.patch.object(
                hook,
                "run_sync_command",
                return_value={"command": "plan", "fetch_errors": 1},
            ) as sync,
        ):
            self.assertEqual(hook.main(), 1)

        sync.assert_called_once_with("plan", paths)

    def test_plan_that_omits_a_staged_file_is_blocked(self) -> None:
        paths = ["detector/CPU.json"]
        with (
            mock.patch.object(hook, "staged_content_paths", return_value=paths),
            mock.patch.object(hook, "unstaged_versions", return_value=[]),
            mock.patch.object(hook, "validate_content"),
            mock.patch.object(
                hook,
                "run_sync_command",
                return_value={
                    "command": "plan",
                    "fetch_errors": 0,
                    "resources": [],
                },
            ) as sync,
        ):
            self.assertEqual(hook.main(), 1)

        sync.assert_called_once_with("plan", paths)

    def test_sync_command_adds_yes_only_for_apply(self) -> None:
        output = json.dumps({"failed_count": 0})
        with mock.patch.object(
            hook, "_run", return_value=completed(stdout=output)
        ) as run:
            hook.run_sync_command("apply", ["detector/CPU.json"])

        command = run.call_args.args[0]
        self.assertEqual(command[-1], "--yes")

    def test_sync_command_parses_json_when_progress_is_on_stderr(self) -> None:
        output = json.dumps({"failed_count": 0, "results": []})
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(
                hook,
                "_run",
                return_value=completed(
                    stdout=output,
                    stderr="  Created chart: New chart\n",
                ),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            payload = hook.run_sync_command("apply", ["group/Kubernetes.json"])

        self.assertEqual(payload, {"failed_count": 0, "results": []})
        self.assertEqual(stdout.getvalue(), output + "\n")
        self.assertIn("Created chart: New chart", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
