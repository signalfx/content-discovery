from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sfx_client


class FakeResponse:
    def __init__(self, status_code: int, body=None) -> None:
        self.status_code = status_code
        self._body = body
        self.content = b"" if body is None else b"json"
        self.text = "" if body is None else str(body)

    def json(self):
        return self._body


class SfxClientTest(unittest.TestCase):
    def test_get_uses_documented_resource_path(self) -> None:
        with mock.patch.object(
            sfx_client, "do_get", return_value=FakeResponse(200, {"id": "1"})
        ) as request:
            result = sfx_client.get_object("dashboard", "1", "https://api", "token")

        request.assert_called_once_with("https://api/v2/dashboard/1", "token")
        self.assertEqual(result, {"id": "1"})

    def test_dedicated_export_is_used_for_navigator(self) -> None:
        with mock.patch.object(
            sfx_client, "do_get", return_value=FakeResponse(200, {"export": True})
        ) as request:
            sfx_client.export_object("navigator", "1", "https://api", "token")

        request.assert_called_once_with("https://api/v2/navigator/1/export", "token")

    def test_chart_export_falls_back_to_get_representation(self) -> None:
        with mock.patch.object(sfx_client, "get_object", return_value={"id": "1"}) as getter:
            result = sfx_client.export_object("chart", "1", "https://api", "token")

        getter.assert_called_once_with("chart", "1", "https://api", "token")
        self.assertEqual(result, {"id": "1"})

    def test_navigator_create_uses_full_model_content_type(self) -> None:
        with mock.patch.object(
            sfx_client, "do_post", return_value=FakeResponse(201, {"id": "1"})
        ) as request:
            sfx_client.create_object("navigator", {"name": "N"}, "https://api", "token")

        request.assert_called_once_with(
            "https://api/v2/navigator",
            "token",
            {"name": "N"},
            "application/json",
        )

    def test_navigator_update_uses_full_model_content_type(self) -> None:
        with mock.patch.object(
            sfx_client, "do_put", return_value=FakeResponse(200, {"id": "1"})
        ) as request:
            sfx_client.update_object(
                "navigator",
                "1",
                {
                    "connectedCategory": "APACHE",
                    "metricClasses": [],
                    "metricColumns": [],
                },
                "https://api",
                "token",
            )

        request.assert_called_once_with(
            "https://api/v2/navigator/1",
            "token",
            {
                "connectedCategory": "APACHE",
                "metricClasses": None,
                "metricColumns": None,
            },
            "application/json",
        )

    def test_navigator_update_preserves_nonempty_metric_arrays(self) -> None:
        payload = {
            "metricClasses": [{"id": "requests"}],
            "metricColumns": [{"metric": "apache.requests"}],
        }
        with mock.patch.object(
            sfx_client, "do_put", return_value=FakeResponse(200, {"id": "1"})
        ) as request:
            sfx_client.update_object(
                "navigator", "1", payload, "https://api", "token"
            )

        self.assertEqual(request.call_args.args[2], payload)

    def test_non_navigator_update_preserves_empty_metric_arrays(self) -> None:
        payload = {"metricClasses": [], "metricColumns": []}
        with mock.patch.object(
            sfx_client, "do_put", return_value=FakeResponse(200, {"id": "1"})
        ) as request:
            sfx_client.update_object("chart", "1", payload, "https://api", "token")

        self.assertEqual(request.call_args.args[2], payload)

    def test_update_is_strict_on_not_found(self) -> None:
        with mock.patch.object(
            sfx_client, "do_put", return_value=FakeResponse(404, {"message": "missing"})
        ):
            with self.assertRaisesRegex(RuntimeError, "not found"):
                sfx_client.update_object(
                    "datalink", "missing", {}, "https://api", "token"
                )

    def test_delete_accepts_no_content(self) -> None:
        with mock.patch.object(
            sfx_client, "do_delete", return_value=FakeResponse(204)
        ) as request:
            result = sfx_client.delete_object("detector", "1", "https://api", "token")

        request.assert_called_once_with("https://api/v2/detector/1", "token")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
