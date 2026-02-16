"""
HTTP client that talks to the Revit Bridge add-in running inside Revit.
The bridge listens on localhost:8080 and accepts JSON command payloads.
"""

import httpx

REVIT_BRIDGE_URL = "http://localhost:8080"
TIMEOUT = 30.0  # Revit operations can take a few seconds


async def send_command(command: str, params: dict | None = None) -> dict:
    """Send a command to the Revit Bridge and return the response."""
    payload = {
        "command": command,
        "params": params or {}
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{REVIT_BRIDGE_URL}/command", json=payload)
        resp.raise_for_status()
        return resp.json()


async def ping() -> bool:
    """Check if the Revit Bridge is running and responsive."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{REVIT_BRIDGE_URL}/ping")
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
