import os
import httpx
from . import mock

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

SECRET_KEYWORDS = ["password", "api_key", "secret", "DATABASE_URL", "AWS_SECRET"]


async def check_github_secrets(domain: str) -> dict:
    """
    Real GitHub code search for the domain alongside common secret keywords.
    Works with zero auth (10 req/min) or a token (30 req/min).
    Returns empty results (not mock) on API failure — fake secrets inflate risk unfairly.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    query = f'"{domain}" (password OR api_key OR secret OR DATABASE_URL)'
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.github.com/search/code",
                headers=headers,
                params={"q": query, "per_page": 10},
            )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            return {
                "hits": [
                    {
                        "repo": item["repository"]["full_name"],
                        "file": item["name"],
                        "url": item["html_url"],
                    }
                    for item in items
                ],
                "source": "live",
            }
    except httpx.HTTPError:
        pass

    # Return empty — do NOT use mock data here. Fake "exposed secrets"
    # carry a 3x risk multiplier and cause false HIGH/CRITICAL ratings.
    return {"hits": [], "source": "unavailable"}
