"""Base API service with common HTTP methods."""

import requests
from typing import Dict, Any


class RemoteNotFound(RuntimeError):
    """A resource id does not exist in the target SignalBuddy env.

    Raised by ``fetch_*_export_by_id`` so callers can distinguish a
    missing-resource (recoverable: maybe create instead) from a
    transport / auth failure (not recoverable here). Keeps the strict
    update / create verbs from silently falling through to the wrong
    operation.
    """


def do_get(url: str, token: str) -> requests.Response:
    """
    Perform a GET request.
    
    Args:
        url: The API endpoint URL
        token: The SignalFx access token
        
    Returns:
        Response object
    """
    return requests.get(url, headers={"X-SF-TOKEN": token, "Accept": "application/json"})


def do_put(url: str, token: str, data: Dict[str, Any]) -> requests.Response:
    """
    Perform a PUT request.
    
    Args:
        url: The API endpoint URL
        token: The SignalFx access token
        data: The JSON data to send
        
    Returns:
        Response object
    """
    return requests.put(url, headers={"X-SF-TOKEN": token, "Content-Type": "application/json"}, json=data)


def do_post(url: str, token: str, data: Dict[str, Any]) -> requests.Response:
    """
    Perform a POST request.
    
    Args:
        url: The API endpoint URL
        token: The SignalFx access token
        data: The JSON data to send
        
    Returns:
        Response object
    """
    return requests.post(url, headers={"X-SF-TOKEN": token, "Content-Type": "application/json"}, json=data)

