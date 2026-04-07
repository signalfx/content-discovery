"""Base API service with common HTTP methods."""

import requests
from typing import Dict, Any


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

