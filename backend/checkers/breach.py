import os
import httpx
from . import mock

HIBP_API_KEY = os.getenv("HIBP_API_KEY", "").strip()


async def check_breaches(target: str, is_email: bool) -> dict:
    """Returns {'breaches': [...], 'source': 'live'|'mock'}"""
    if HIBP_API_KEY and is_email:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://haveibeenpwned.com/api/v3/breachedaccount/{target}",
                    headers={"hibp-api-key": HIBP_API_KEY, "user-agent": "DarkWebWatchdog"},
                    params={"truncateResponse": "false"},
                )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "breaches": [
                        {
                            "name": b.get("Title", b.get("Name")),
                            "year": int(b.get("BreachDate", "0000")[:4]) if b.get("BreachDate") else None,
                            "data": b.get("DataClasses", []),
                            "exposed_records": f"{b.get('PwnCount', 0):,}",
                        }
                        for b in data
                    ],
                    "source": "live",
                }
            if resp.status_code == 404:
                return {"breaches": [], "source": "live"}
            # Any other status (401, 429, etc.) — fall through to mock
        except httpx.HTTPError:
            pass

    return {"breaches": mock.mock_breaches(target), "source": "mock"}
