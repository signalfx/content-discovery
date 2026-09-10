"""Strict read, create, update, and export client for SignalFx content objects."""

from __future__ import annotations

from typing import Any, Dict

from sfx_http import RemoteNotFound, do_get, do_post, do_put


RESOURCE_PATHS = {
    "navigator": "navigator",
    "detector": "detector",
    "datalink": "crosslink",
    "dashboard-group": "dashboardgroup",
    "chart": "chart",
    "dashboard": "dashboard",
}

# These export endpoints are used by the existing content synchronization
# services. The attached object OpenAPI specs do not define a distinct export
# endpoint for data links, charts, or dashboards, so those use their GET form.
DEDICATED_EXPORT_RESOURCES = {"navigator", "detector", "dashboard-group"}

SERVER_MANAGED_FIELDS = ("id", "created", "creator", "lastUpdated", "lastUpdatedBy")
NAVIGATOR_NULLABLE_ARRAY_FIELDS = ("metricClasses", "metricColumns")


def prepare_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Copy an exported object and remove fields managed by the API."""
    prepared = dict(payload)
    for field in SERVER_MANAGED_FIELDS:
        prepared.pop(field, None)
    return prepared


def _prepare_update_payload(resource: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize API constraints without changing the exported local object."""
    prepared = dict(payload)
    if resource == "navigator":
        for field in NAVIGATOR_NULLABLE_ARRAY_FIELDS:
            if prepared.get(field) == []:
                prepared[field] = None
    return prepared


def _path(resource: str) -> str:
    try:
        return RESOURCE_PATHS[resource]
    except KeyError as exc:
        raise ValueError(f"unsupported SFX resource: {resource}") from exc


def _body(response: Any) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _require_success(
    response: Any,
    expected: tuple[int, ...],
    action: str,
    resource: str,
    resource_id: str | None = None,
) -> Any:
    label = f"{resource} {resource_id}" if resource_id else resource
    if response.status_code == 404:
        raise RemoteNotFound(f"{label} not found")
    if response.status_code not in expected:
        raise RuntimeError(
            f"Failed to {action} {label}: HTTP {response.status_code}: {response.text}"
        )
    return _body(response)


def get_object(resource: str, resource_id: str, base_url: str, token: str) -> Any:
    response = do_get(f"{base_url}/v2/{_path(resource)}/{resource_id}", token)
    return _require_success(response, (200,), "get", resource, resource_id)


def export_object(resource: str, resource_id: str, base_url: str, token: str) -> Any:
    if resource not in DEDICATED_EXPORT_RESOURCES:
        return get_object(resource, resource_id, base_url, token)
    response = do_get(
        f"{base_url}/v2/{_path(resource)}/{resource_id}/export", token
    )
    return _require_success(response, (200,), "export", resource, resource_id)


def create_object(
    resource: str, payload: Dict[str, Any], base_url: str, token: str
) -> Any:
    response = do_post(
        f"{base_url}/v2/{_path(resource)}",
        token,
        payload,
        "application/json",
    )
    return _require_success(response, (200, 201), "create", resource)


def update_object(
    resource: str,
    resource_id: str,
    payload: Dict[str, Any],
    base_url: str,
    token: str,
) -> Any:
    request_payload = _prepare_update_payload(resource, payload)
    response = do_put(
        f"{base_url}/v2/{_path(resource)}/{resource_id}",
        token,
        request_payload,
        "application/json",
    )
    return _require_success(response, (200,), "update", resource, resource_id)
