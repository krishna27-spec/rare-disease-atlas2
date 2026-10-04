"""The one place the live app uses the LLM: turn cited candidate actions into 1-3 plain-language steps.

If the LLM is down, or its answer cites nothing valid, the caller shows the candidate list instead."""
import json
import os

from src.webapp.data import EDGE_ID, validate_steps

PROMPT = """You help the parent of a child with a rare disease. Below are CANDIDATE ACTIONS found in a
knowledge graph. Write 1 to 3 next steps for a parent with no medical background, in plain language, ONE STEP PER LINE
(each line a full sentence that ends with its edge IDs; no other text).
Rules: use only the facts in the candidates; after every claim put the supporting edge IDs in square brackets,
like [E1a2b3c4d5e6f]; never invent names, dates or numbers; do not give medical advice or treatment advice.
If the candidates are empty, reply exactly: No supported next step was found.

Disease: {disease}
Candidates (JSON): {candidates}"""


def _load_secrets() -> None:
    try:
        import streamlit as st
        for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
            if k in st.secrets and k not in os.environ:
                os.environ[k] = str(st.secrets[k])
    except Exception:  # no secrets file locally: .env is used instead
        pass


def next_steps(disease: str, candidates: list[dict]) -> dict:
    """Returns {"steps": [...], "used_llm": bool, "error": str}."""
    allowed = {i for c in candidates for i in c["edge_ids"]}
    if not candidates:
        return {"steps": [], "used_llm": False, "error": ""}
    _load_secrets()
    try:
        from src.llm import chat
        text = chat([{"role": "user", "content": PROMPT.format(
            disease=disease, candidates=json.dumps(candidates, ensure_ascii=False))}], tier="quality", max_wait=20)
        steps = validate_steps(text, allowed)
        if steps:
            return {"steps": steps[:3], "used_llm": True, "error": ""}
        return {"steps": [], "used_llm": False, "error": "The AI answer had no citations we could verify."}
    except Exception as e:  # the tab must never break
        return {"steps": [], "used_llm": False, "error": f"AI explanation unavailable ({type(e).__name__})."}
