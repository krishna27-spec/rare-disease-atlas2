"""One simple way to talk to the LLM (OpenAI gpt-oss), on whichever provider is available right now.

Providers come from .env and are tried in order:
  1. the main one: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (Groq by default)
  2. OpenRouter, if OPENROUTER_API_KEY is set
Two tiers pick the model size:
  tier="bulk"     the small model (gpt-oss-20b) first, the big one when the small one is rate-limited
  tier="quality"  the big model (gpt-oss-120b) first, then the small one if the big one is not available
(Groq counts each model's rate limit separately, so falling over to the other size doubles throughput.)
A provider that says 'slow down' (HTTP 429) or fails is rested for a while and the next one is used.
`last_model()` tells which model answered the latest call in this thread, so results can record it.
"""
import json
import os
import re
import threading
import time

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, BadRequestError, OpenAI, RateLimitError
from pydantic import BaseModel

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1"
MAX_WAIT = 300          # default seconds to wait in total for some provider to be free again (batch jobs)
_resting: dict[tuple[str, str], float] = {}   # (provider, model) -> time it may be used again
_lock = threading.Lock()
_used = threading.local()


def _candidates(tier: str) -> list[tuple[str, str, str, str]]:
    """(provider name, base_url, api_key, model), best first."""
    providers = []
    if os.environ.get("LLM_API_KEY"):
        providers.append(("main", os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"],
                          os.environ["LLM_MODEL"], os.environ.get("LLM_MODEL_QUALITY", "openai/gpt-oss-120b")))
    if os.environ.get("OPENROUTER_API_KEY"):
        providers.append(("openrouter", OPENROUTER_URL, os.environ["OPENROUTER_API_KEY"],
                          os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b"),
                          os.environ.get("OPENROUTER_MODEL_QUALITY", "openai/gpt-oss-120b")))
    if not providers:
        raise RuntimeError("No LLM configured: set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env")
    small = [(n, url, key, s) for n, url, key, s, _ in providers]
    big = [(n, url, key, b) for n, url, key, _, b in providers]
    return big + small if tier == "quality" else small + big


def _rest_seconds(err: Exception) -> float:
    """How long to leave a provider alone after an error."""
    msg = str(err).lower()
    if isinstance(err, RateLimitError):
        m = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", msg)   # Groq says exactly how long
        if m:
            return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + float(m.group(3)) + 1
        daily = "per day" in msg or "tpd" in msg or "rpd" in msg or "free-models-per-day" in msg
        return 3600 if daily else 20
    return 600                                            # wrong key, no credit, model missing, server down


def _ask(messages: list[dict], json_schema: dict | None, tier: str = "bulk", effort: str | None = None,
         max_wait: float = MAX_WAIT) -> str:
    """Send one request to the first provider that is not resting; move on when one refuses."""
    kwargs = {}
    if json_schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "answer", "schema": json_schema},
        }
    if effort:                 # gpt-oss thinks before answering; "low" uses far fewer tokens per call
        kwargs["reasoning_effort"] = effort
    cands = _candidates(tier)
    deadline = time.time() + max_wait
    last_error: Exception | None = None
    while True:
        now = time.time()
        free = [c for c in cands if _resting.get((c[0], c[3]), 0) <= now]
        if not free:
            wake = min(_resting[(c[0], c[3])] for c in cands)
            if wake > deadline:
                raise RuntimeError(f"No LLM provider available (last error: {last_error})")
            time.sleep(max(wake - now, 0.5))
            continue
        name, url, key, model = free[0]
        try:
            reply = OpenAI(base_url=url, api_key=key, max_retries=0, timeout=120).chat.completions.create(
                model=model, messages=messages, **kwargs)
            _used.model = f"{model} ({name})" if name != "main" else model
            return reply.choices[0].message.content or ""
        except BadRequestError:
            raise                                         # our request or the model's JSON was bad: caller decides
        except (RateLimitError, APIStatusError, APIConnectionError) as e:
            last_error = e
            with _lock:
                _resting[(name, model)] = time.time() + _rest_seconds(e)


def last_model() -> str:
    """The model that answered the latest call made from this thread ('' if none yet)."""
    return getattr(_used, "model", "")


def chat(messages: list[dict], json_schema: dict | None = None, tier: str = "bulk", effort: str | None = None,
         max_wait: float = MAX_WAIT) -> str:
    """Return the model's reply text. Pass json_schema to ask for JSON output.

    max_wait: seconds to keep waiting for a rate-limited provider; keep it short for anything a user is waiting on."""
    return _ask(messages, json_schema, tier, effort, max_wait)


def chat_json(messages: list[dict], model_class: type[BaseModel], tier: str = "bulk",
              effort: str | None = None) -> BaseModel | None:
    """Ask for JSON, validate with Pydantic, retry once, then give up (None) and log."""
    schema = model_class.model_json_schema()
    for _ in range(2):
        try:
            text = _ask(messages, schema, tier, effort)
        except BadRequestError:  # e.g. Groq 400 json_validate_failed: the model produced no valid JSON
            continue
        try:
            return model_class.model_validate(json.loads(text))
        except ValueError:  # bad JSON or failed validation
            continue
    print("chat_json: invalid JSON twice, skipping.")
    return None
