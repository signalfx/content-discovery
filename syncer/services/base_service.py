"""Base API service with common HTTP methods."""

import os
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


# Default request timeouts (connect, read) in seconds. Bounded so a
# stalled SignalFx endpoint can't make ``plan`` / ``apply`` / ``update``
# / ``pull`` hang indefinitely; instead the transport failure is
# converted to ``RuntimeError`` and the CLI surfaces it as a structured
# API failure (exit code 4).
#
# Tunable for slow networks or batched POSTs via the
# ``SIGNALBUDDY_HTTP_TIMEOUT`` env var. Format is either a single float
# (applied to both connect and read) or ``<connect>,<read>``.
_DEFAULT_TIMEOUT: tuple[float, float] = (10.0, 60.0)


def _resolve_timeout() -> tuple[float, float]:
    raw = os.environ.get("SIGNALBUDDY_HTTP_TIMEOUT")
    if not raw:
        return _DEFAULT_TIMEOUT
    try:
        if "," in raw:
            connect_s, read_s = raw.split(",", 1)
            return (float(connect_s.strip()), float(read_s.strip()))
        single = float(raw.strip())
        return (single, single)
    except ValueError:
        # Fall back to defaults rather than crashing the CLI on a
        # malformed env var; the user-facing error stays in band.
        return _DEFAULT_TIMEOUT


def _request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """Internal wrapper that applies a bounded timeout to every call.

    Converts ``requests.Timeout`` / ``requests.ConnectionError`` /
    other transport-level ``requests.RequestException`` instances to a
    plain ``RuntimeError`` so callers don't need a ``requests``
    dependency in their exception-handling paths and so the CLI's
    existing API-failure mapping (``EXIT_API_FAILURE = 4``) kicks in.
    """
    kwargs.setdefault("timeout", _resolve_timeout())
    try:
        return requests.request(method, url, **kwargs)
    except requests.exceptions.Timeout as e:
        raise RuntimeError(
            f"timed out talking to SignalBuddy ({method} {url}); "
            f"raise SIGNALBUDDY_HTTP_TIMEOUT if this is expected: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"transport error talking to SignalBuddy ({method} {url}): {e}"
        ) from e


def do_get(url: str, token: str) -> requests.Response:
    """
    Perform a GET request.

    Args:
        url: The API endpoint URL
        token: The SignalFx access token

    Returns:
        Response object

    Raises:
        RuntimeError: On connection, timeout, or other transport-level
            failures. Status-code-based errors are still left to the
            caller to interpret.
    """
    return _request(
        "GET",
        url,
        headers={"X-SF-TOKEN": token, "Accept": "application/json"},
    )


def do_put(url: str, token: str, data: Dict[str, Any]) -> requests.Response:
    """
    Perform a PUT request.

    Args:
        url: The API endpoint URL
        token: The SignalFx access token
        data: The JSON data to send

    Returns:
        Response object

    Raises:
        RuntimeError: On connection, timeout, or other transport-level
            failures. Status-code-based errors are still left to the
            caller to interpret.
    """
    return _request(
        "PUT",
        url,
        headers={"X-SF-TOKEN": token, "Content-Type": "application/json"},
        json=data,
    )


def do_post(url: str, token: str, data: Dict[str, Any]) -> requests.Response:
    """
    Perform a POST request.

    Args:
        url: The API endpoint URL
        token: The SignalFx access token
        data: The JSON data to send

    Returns:
        Response object

    Raises:
        RuntimeError: On connection, timeout, or other transport-level
            failures. Status-code-based errors are still left to the
            caller to interpret.
    """
    return _request(
        "POST",
        url,
        headers={"X-SF-TOKEN": token, "Content-Type": "application/json"},
        json=data,
    )
