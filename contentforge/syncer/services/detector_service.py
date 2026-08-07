"""Detector API service for fetching and updating detectors."""

import sys
from typing import Dict, Any
from .base_service import do_get, do_put, do_post, RemoteNotFound

# Server-managed fields stripped on create — same rationale as in
# navigator_service. Kept inline (not imported) so each service module
# stays self-contained and explicit about its create payload shape.
_CREATE_STRIP_FIELDS = ("id", "created", "creator", "lastUpdated", "lastUpdatedBy")


def fetch_detector_export_by_id(detector_id: str, base_url: str, token: str, format: str = "json") -> Any:
    """
    Fetch a detector export by ID.
    
    Args:
        detector_id: The detector ID
        base_url: The base API URL
        token: The SignalFx access token
        format: Return format, either "json" or "text"
        
    Returns:
        The exported detector data
        
    Raises:
        RemoteNotFound: If the detector does not exist (HTTP 404)
        RuntimeError: For any other non-200 response
    """
    resp = do_get(f"{base_url}/v2/detector/{detector_id}/export", token)
    if resp.status_code == 404:
        raise RemoteNotFound(f"detector {detector_id} not found")
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch detector {detector_id}: {resp.text}")
    if format == "json":
        return resp.json()
    return resp.text


def create_detector(
    detector_export: Dict[str, Any], base_url: str, token: str
) -> Dict[str, Any]:
    """Create a detector in the target env from a detector export blob.

    Strips server-managed fields from the inner ``detector`` object so
    the backend assigns a fresh id and timestamps. Returns the parsed
    response for caller-side id capture.
    """
    detector = dict(detector_export["detectorExport"]["detector"])
    for field in _CREATE_STRIP_FIELDS:
        detector.pop(field, None)

    resp = do_post(f"{base_url}/v2/detector", token, detector)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create detector: {resp.status_code} {resp.text}"
        )
    return resp.json()


def update_detector(detector_export: Dict[str, Any], base_url: str, token: str) -> bool:
    """
    Update a detector using the detectorExport object.
    
    Args:
        detector_export: The detector export data
        base_url: The base API URL
        token: The SignalFx access token
        
    Returns:
        True if successful, False otherwise
    """
    detector = detector_export["detectorExport"]["detector"]
    detector_id = detector["id"]

    # Strict update: never silently auto-create on 404. A stale or
    # deleted detector id must surface as a failure so the caller can
    # decide whether to invoke ``create`` explicitly.
    resp = do_put(f"{base_url}/v2/detector/{detector_id}", token, detector)
    if resp.status_code in [200, 201]:
        print(f"Updated detector: {detector.get('name', detector_id)}")
        return True
    elif resp.status_code == 404:
        print(
            f"Failed to update detector {detector_id}: not found in master; "
            f"use 'create' instead of 'update' / 'apply'",
            file=sys.stderr,
        )
        return False
    else:
        print(f"Failed to update detector {detector_id}: {resp.text}", file=sys.stderr)
        return False

