import os
import httpx
from . import mock

SHODAN_API_KEY = os.getenv("SHODAN_API_KEY", "").strip()


async def check_exposed_infra(domain: str) -> dict:
    if SHODAN_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.shodan.io/dns/domain/" + domain,
                    params={"key": SHODAN_API_KEY},
                )
            if resp.status_code == 200:
                data = resp.json()
                subdomains = data.get("subdomains", [])[:10]
                return {
                    "exposures": [{"service": "Subdomain on record", "ip": s} for s in subdomains],
                    "source": "live",
                }
        except httpx.HTTPError:
            pass

    return {"exposures": mock.mock_shodan_exposure(domain), "source": "mock"}
