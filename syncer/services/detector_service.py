"""Detector API service for fetching and updating detectors."""

import sys
from typing import Dict, Any
from .base_service import do_get, do_put, do_post


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
        RuntimeError: If the fetch fails
    """
    resp = do_get(f"{base_url}/v2/detector/{detector_id}/export", token)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch detector {detector_id}: {resp.text}")
    if format == "json":
        return resp.json()
    return resp.text


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
    
    resp = do_put(f"{base_url}/v2/detector/{detector_id}", token, detector)
    if resp.status_code in [200, 201]:
        print(f"Updated detector: {detector.get('name', detector_id)}")
        return True
    elif resp.status_code == 404:
        # Detector doesn't exist, create it
        resp = do_post(f"{base_url}/v2/detector", token, detector)
        if resp.status_code in [200, 201]:
            print(f"Created detector: {detector.get('name', detector_id)}")
            return True
        else:
            print(f"Failed to create detector {detector_id}: {resp.text}", file=sys.stderr)
            return False
    else:
        print(f"Failed to update detector {detector_id}: {resp.text}", file=sys.stderr)
        return False

