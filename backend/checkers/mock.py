"""
Deterministic mock-data generator.

Every checker falls back to this when its API key isn't configured, so the
whole platform is demoable with zero setup. Output is seeded from the
target string, so the same input always produces the same "breach", which
keeps a live demo from looking random or fake when you re-scan something.
"""
import hashlib
import random


def seeded_random(target: str, salt: str) -> random.Random:
    seed = hashlib.sha256(f"{target}:{salt}".encode()).hexdigest()
    return random.Random(seed)


BREACH_CATALOG = [
    {"name": "Collection#1 Compilation", "year": 2019, "data": ["Emails", "Passwords"]},
    {"name": "LinkedIn Scrape", "year": 2021, "data": ["Emails", "Job titles", "Phone numbers"]},
    {"name": "Adobe Breach", "year": 2013, "data": ["Emails", "Password hints", "Encrypted passwords"]},
    {"name": "Canva Data Breach", "year": 2019, "data": ["Emails", "Usernames", "Passwords"]},
    {"name": "Dropbox Leak", "year": 2016, "data": ["Emails", "Passwords"]},
    {"name": "MyFitnessPal Breach", "year": 2018, "data": ["Emails", "Usernames", "Passwords"]},
    {"name": "Exactis Marketing Leak", "year": 2018, "data": ["Emails", "Phone numbers", "Personal profiles"]},
]

PHISHING_PATTERNS = [
    "{brand}-login-support.com",
    "secure-{brand}.net",
    "{brand}verify-account.com",
    "{brand}-billing-update.info",
]

RANSOMWARE_GROUPS = ["LockBit", "BlackCat/ALPHV", "Clop", "Play", "Akira", "8Base"]

SECRET_TYPES = [
    "AWS Access Key", "Stripe Live Secret Key", "Database connection string",
    "Slack Webhook URL", "Private SSH key", "Google API Key", "JWT signing secret",
]


def mock_breaches(target: str) -> list[dict]:
    rng = seeded_random(target, "breaches")
    # Very conservative: since this is mock/demo data, almost always return 0
    # to avoid false-positive breach alerts on real email addresses.
    count = rng.choices([0, 1, 2], weights=[85, 12, 3])[0]
    return [
        {**b, "exposed_records": rng.choice(["thousands", "millions", "10M+"])}
        for b in rng.sample(BREACH_CATALOG, k=min(count, len(BREACH_CATALOG)))
    ]


def mock_phishing_domains(target_domain: str) -> list[dict]:
    rng = seeded_random(target_domain, "phishing")
    brand = target_domain.split(".")[0]
    # Most domains have 0-1 look-alikes found in practice.
    count = rng.choices([0, 1, 2, 3], weights=[55, 28, 12, 5])[0]
    picks = rng.sample(PHISHING_PATTERNS, k=min(count, len(PHISHING_PATTERNS)))
    return [
        {
            "domain": p.format(brand=brand),
            "first_seen_days_ago": rng.randint(2, 240),
            "status": rng.choice(["Active", "Active", "Sinkholed", "Parked"]),
        }
        for p in picks
    ]


def mock_ransomware_mentions(target: str) -> list[dict]:
    rng = seeded_random(target, "ransomware")
    # Ransomware mentions are very rare in reality — only ~5% of targets.
    if rng.random() > 0.95:
        group = rng.choice(RANSOMWARE_GROUPS)
        return [{
            "group": group,
            "context": "Named on leak-site listing page",
            "posted_days_ago": rng.randint(1, 90),
        }]
    return []


def mock_github_secrets(target: str) -> list[dict]:
    rng = seeded_random(target, "github")
    # Most targets have 0 exposed secrets — only flag occasionally.
    count = rng.choices([0, 1, 2, 3], weights=[65, 22, 10, 3])[0]
    return [
        {
            "repo": f"{rng.choice(['legacy-scripts', 'infra-tools', 'internal-poc', 'demo-app'])}",
            "file": rng.choice(["config.py", ".env.bak", "deploy.sh", "settings.yml"]),
            "secret_type": rng.choice(SECRET_TYPES),
            "commit_age_days": rng.randint(1, 700),
        }
        for _ in range(count)
    ]


def mock_shodan_exposure(target_domain: str) -> list[dict]:
    rng = seeded_random(target_domain, "shodan")
    # Most domains have no publicly exposed services.
    count = rng.choices([0, 1, 2], weights=[65, 28, 7])[0]
    services = ["Exposed RDP (3389)", "Open Elasticsearch (9200)", "Unpatched VPN endpoint",
                "Exposed MongoDB (27017)", "Outdated Apache (CVE-flagged)"]
    return [
        {"service": s, "ip": f"{rng.randint(20,220)}.{rng.randint(1,254)}.{rng.randint(1,254)}.{rng.randint(1,254)}"}
        for s in rng.sample(services, k=min(count, len(services)))
    ]
