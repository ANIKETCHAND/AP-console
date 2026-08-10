import os
import httpx
from . import mock

VT_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "").strip()


async def check_domain_reputation(domain: str) -> dict:
    """Live VirusTotal reputation for the domain itself, if a key is set."""
    if VT_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://www.virustotal.com/api/v3/domains/{domain}",
                    headers={"x-apikey": VT_API_KEY},
                )
            if resp.status_code == 200:
                stats = resp.json()["data"]["attributes"]["last_analysis_stats"]
                return {
                    "malicious_votes": stats.get("malicious", 0),
                    "suspicious_votes": stats.get("suspicious", 0),
                    "source": "live",
                }
        except (httpx.HTTPError, KeyError):
            pass
    return {"malicious_votes": None, "suspicious_votes": None, "source": "unavailable"}


async def check_lookalike_domains(domain: str) -> dict:
    """
    Lookalike/typosquat domain discovery. No free real-time registry API exists
    for this, so this stays mock-driven — clearly labeled as such in the response.
    """
    return {"domains": mock.mock_phishing_domains(domain), "source": "mock"}
