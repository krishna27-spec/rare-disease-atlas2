"""Search terms per disease, and the rule that decides which disease a trial/grant text is about.

SPECIFIC terms name one disease (e.g. "MPS IIIA"). BROAD terms name a whole family
(e.g. "Sanfilippo syndrome") and are used only when a text names no specific disease.
Terms are lowercase with hyphens as spaces; they are matched on whole words.
"""
import re

SPECIFIC = {
    "MONDO:0009655": ["sanfilippo syndrome type a", "sanfilippo a", "mucopolysaccharidosis iiia",
                      "mucopolysaccharidosis type iiia", "mucopolysaccharidosis type 3a", "mps iiia", "mps 3a",
                      "sgsh deficiency"],
    "MONDO:0009656": ["sanfilippo syndrome type b", "sanfilippo b", "mucopolysaccharidosis iiib",
                      "mucopolysaccharidosis type iiib", "mucopolysaccharidosis type 3b", "mps iiib", "mps 3b",
                      "naglu deficiency"],
    "MONDO:0009657": ["sanfilippo syndrome type c", "sanfilippo c", "mucopolysaccharidosis iiic",
                      "mucopolysaccharidosis type iiic", "mucopolysaccharidosis type 3c", "mps iiic", "mps 3c",
                      "hgsnat"],
    "MONDO:0009658": ["sanfilippo syndrome type d", "sanfilippo d", "mucopolysaccharidosis iiid",
                      "mucopolysaccharidosis type iiid", "mucopolysaccharidosis type 3d", "mps iiid", "mps 3d"],
    "MONDO:0009744": ["cln1 disease", "cln1", "ppt1 deficiency", "infantile neuronal ceroid lipofuscinosis",
                      "santavuori haltia"],
    "MONDO:0008769": ["cln2 disease", "cln2", "tpp1 deficiency", "late infantile neuronal ceroid lipofuscinosis",
                      "jansky bielschowsky", "cerliponase alfa"],
    "MONDO:0008767": ["cln3 disease", "cln3", "juvenile neuronal ceroid lipofuscinosis", "juvenile batten disease",
                      "spielmeyer vogt"],
    "MONDO:0009745": ["cln5 disease", "cln5"],
    "MONDO:0011144": ["cln6 disease", "cln6"],
    "MONDO:0012588": ["cln7 disease", "cln7", "mfsd8"],
    "MONDO:0010830": ["cln8 disease", "cln8"],
    "MONDO:0009757": ["niemann pick disease type c1", "niemann pick type c1", "npc1 disease", "npc1 deficiency"],
    "MONDO:0011873": ["niemann pick disease type c2", "niemann pick type c2", "npc2 disease", "npc2 deficiency"],
    "MONDO:0018149": ["gm1 gangliosidosis", "gm1 gangliosidoses"],
    "MONDO:0010100": ["tay sachs disease", "tay sachs", "hexa deficiency"],
    "MONDO:0010006": ["sandhoff disease", "sandhoff"],
    "MONDO:0018868": ["metachromatic leukodystrophy"],
    "MONDO:0009499": ["krabbe disease", "krabbe", "globoid cell leukodystrophy", "galc deficiency"],
    "MONDO:0009561": ["alpha mannosidosis"],
    "MONDO:0009653": ["mucolipidosis type iv", "mucolipidosis iv", "mucolipidosis type 4"],
    "MONDO:0001586": ["mucopolysaccharidosis type i", "mucopolysaccharidosis i", "mps i", "mps 1",
                      "hurler syndrome", "hurler scheie", "scheie syndrome"],
    "MONDO:0010674": ["mucopolysaccharidosis type ii", "mucopolysaccharidosis ii", "mps ii", "mps 2",
                      "hunter syndrome"],
}

_SANFILIPPO = ["MONDO:0009655", "MONDO:0009656", "MONDO:0009657", "MONDO:0009658"]
_NCL = ["MONDO:0009744", "MONDO:0008769", "MONDO:0008767", "MONDO:0009745", "MONDO:0011144",
        "MONDO:0012588", "MONDO:0010830"]
BROAD = [  # (terms, diseases the family covers)
    (["sanfilippo syndrome", "sanfilippo", "mucopolysaccharidosis iii", "mucopolysaccharidosis type iii",
      "mps iii", "mps 3"], _SANFILIPPO),
    (["neuronal ceroid lipofuscinosis", "neuronal ceroid lipofuscinoses", "batten disease"], _NCL),
    (["niemann pick disease type c", "niemann pick type c", "niemann pick c"],
     ["MONDO:0009757", "MONDO:0011873"]),
    (["gm2 gangliosidosis", "gm2 gangliosidoses"], ["MONDO:0010100", "MONDO:0010006"]),
]


def normalise(text: str) -> str:
    """Lowercase, hyphens and punctuation become spaces, so 'Tay-Sachs' matches 'tay sachs'."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9α]+", " ", text.lower())).strip()


def _has(text: str, terms: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(t)}\b", text) for t in terms)


def match_diseases(text: str) -> list[tuple[str, str]]:
    """Which of our diseases is this text about? Returns [(mondo_id, 'specific' | 'broad')].

    Specific matches win. A broad (family) match counts only if no specific disease was named."""
    t = normalise(text)
    specific = [(d, "specific") for d, terms in SPECIFIC.items() if _has(t, terms)]
    if specific:
        return specific
    return [(d, "broad") for terms, members in BROAD if _has(t, terms) for d in members]


def search_phrases(mondo_id: str) -> list[str]:
    """Phrases used to ask the APIs (specific terms only)."""
    return SPECIFIC[mondo_id]


def all_phrases() -> list[str]:
    """Every phrase worth searching for (specific and family-wide), without repeats."""
    out = [p for terms in SPECIFIC.values() for p in terms]
    out += [p for terms, _ in BROAD for p in terms]
    return list(dict.fromkeys(out))
