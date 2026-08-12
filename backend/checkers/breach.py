import os
import re
import httpx
from . import mock

HIBP_API_KEY = os.getenv("HIBP_API_KEY", "").strip()


def _extract_email_year(target: str) -> int | None:
    """
    Try to guess the email account creation year from common patterns
    in the local part (e.g. john2024@gmail.com → 2024).
    Returns None if no year found.
    """
    # Match 4-digit years between 2000 and current year
    import datetime
    current_year = datetime.datetime.now().year
    matches = re.findall(r'(20\d{2})', target.split("@")[0])
    years = [int(y) for y in matches if 2000 <= int(y) <= current_year]
    return max(years) if years else None


async def check_breaches(target: str, is_email: bool) -> dict:
    """Returns {'breaches': [...], 'source': 'live'|'mock'}"""

    # Extract the suspected account creation year from the email address
    creation_year = _extract_email_year(target) if is_email else None

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
                breaches = [
                    {
                        "name": b.get("Title", b.get("Name")),
                        "year": int(b.get("BreachDate", "0000")[:4]) if b.get("BreachDate") else None,
                        "data": b.get("DataClasses", []),
                        "exposed_records": f"{b.get('PwnCount', 0):,}",
                    }
                    for b in data
                ]
                # Filter out breaches that predate the email's likely creation year
                if creation_year:
                    breaches = [b for b in breaches if b["year"] is None or b["year"] >= creation_year]
                return {"breaches": breaches, "source": "live"}
            if resp.status_code == 404:
                return {"breaches": [], "source": "live"}
            # Any other status (401, 429, etc.) — fall through to mock
        except httpx.HTTPError:
            pass

    mock_results = mock.mock_breaches(target)
    # Filter mock breaches: if the email has a year pattern, remove breaches before that year
    if creation_year:
        mock_results = [b for b in mock_results if b.get("year") is None or b["year"] >= creation_year]
    return {"breaches": mock_results, "source": "mock"}
