"""
AI summary + chatbot powered by Groq (primary) → OpenAI (fallback) → template.

Groq exposes an OpenAI-compatible REST API, so we reuse the same AsyncOpenAI
client with a different base_url — no extra SDK needed.
"""

import os
import json

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI

# ── Groq (primary — free, fast Llama 3.3 70B) ───────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
_groq = None
if GROQ_API_KEY:
    _groq = AsyncOpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
    )

# ── OpenAI (fallback) ────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
_openai = None
if OPENAI_API_KEY:
    _openai = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def _chat(messages: list, max_tokens: int = 400) -> str | None:
    """Try Groq first, then OpenAI. Returns the reply text or None."""
    # 1. Groq
    if _groq:
        try:
            resp = await _groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[ai_summary] Groq error: {type(e).__name__}: {e}")

    # 2. OpenAI fallback
    if _openai:
        try:
            resp = await _openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"[ai_summary] OpenAI error: {type(e).__name__}: {e}")

    return None


# ── Template fallbacks (used when both AI providers are unavailable) ──────────

def _template_summary(target: str, scan: dict) -> str:
    lines = []
    n_breaches = len(scan["breaches"])
    n_phish = len(scan["phishing_domains"])
    n_secrets = len(scan["github_secrets"])
    n_infra = len(scan["exposed_infra"])
    n_ransom = len(scan["ransomware_mentions"])

    lines.append(f"{target} was checked against {n_breaches} breach record(s), "
                 f"{n_phish} look-alike domain(s), {n_secrets} exposed code secret(s), "
                 f"{n_infra} exposed service(s), and {n_ransom} ransomware leak-site mention(s).")

    if n_breaches:
        names = ", ".join(b["name"] for b in scan["breaches"][:3])
        lines.append(f"Most concerning breaches: {names}.")
    if n_secrets:
        lines.append("Live credentials or keys may be sitting in public repositories — treat these as compromised.")
    if n_phish:
        lines.append("Active look-alike domains can be used to phish employees or customers right now.")
    if n_ransom:
        lines.append("A ransomware group has referenced this target — this warrants immediate escalation.")
    if scan["risk_level"] in ("HIGH", "CRITICAL"):
        lines.append("Recommended: force a password reset org-wide, enforce MFA, and rotate any exposed API keys today.")
    else:
        lines.append("No urgent exposure found, but keep monitoring — dark web listings change daily.")

    return " ".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

async def summarize(target: str, scan: dict) -> dict:
    """Returns {'summary': str, 'source': 'live'|'template'}"""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a cybersecurity threat-intel analyst. "
                "Write clear, concise analysis for non-technical business owners."
            ),
        },
        {
            "role": "user",
            "content": (
                "Given this JSON scan result, write a 3-5 sentence executive summary, "
                "then a bulleted list of the 3 most important immediate actions. "
                "Be direct and concrete — no filler.\n\n"
                f"Target: {target}\n"
                f"Scan JSON:\n{json.dumps(scan, default=str)}"
            ),
        },
    ]
    reply = await _chat(messages, max_tokens=400)
    if reply:
        return {"summary": reply, "source": "live"}
    return {"summary": _template_summary(target, scan), "source": "template"}


async def explain_threat(question: str, scan: dict) -> dict:
    """Chatbot 'explain this threat' endpoint."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a friendly cybersecurity assistant embedded in a threat-intel dashboard. "
                "Answer questions about scan results clearly, in plain language, in 2-4 sentences."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Scan JSON:\n{json.dumps(scan, default=str)}\n\n"
                f"Question: {question}"
            ),
        },
    ]
    reply = await _chat(messages, max_tokens=300)
    if reply:
        return {"answer": reply, "source": "live"}

    # Template fallback
    q = question.lower()
    if "breach" in q:
        answer = ("A breach means this target's data appeared in a dataset stolen from another "
                   "service and later published or traded. It doesn't mean this specific system was "
                   "hacked — but any reused passwords should be rotated everywhere.")
    elif "secret" in q or "github" in q or "key" in q:
        answer = ("Exposed secrets are credentials (API keys, database URLs, tokens) accidentally "
                   "committed to a public code repository. Anyone can copy and use them — rotate the "
                   "credential immediately and scrub it from git history.")
    elif "phishing" in q or "domain" in q:
        answer = ("Look-alike domains mimic a trusted brand to trick employees or customers into "
                   "entering credentials or payment details. Report them to the registrar and warn staff.")
    elif "ransomware" in q:
        answer = ("A ransomware leak-site mention means an attacker group claims to hold stolen data "
                   "and may be pressuring for payment. Engage incident response immediately.")
    else:
        answer = ("This finding indicates a potential exposure. Add a working AI API key (Groq is free) "
                   "for a tailored, LLM-generated explanation of this specific result.")
    return {"answer": answer, "source": "template"}
