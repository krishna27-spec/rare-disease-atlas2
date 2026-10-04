"""Names for our genes (HGNC symbol, previous/alias symbols, full and alias names) -> HGNC symbol.

Only genes already in the graph are included, so a protein name like "tripeptidyl-peptidase I" maps to TPP1."""
import pandas as pd

from src.etl.download import RAW
from src.etl.terms import normalise


def gene_aliases(symbols: set[str]) -> dict[str, str]:
    """normalised name -> HGNC symbol. A name that points at two of our genes is dropped."""
    hg = pd.read_csv(RAW / "hgnc_complete_set.txt", sep="\t", dtype=str, low_memory=False)
    hg = hg[hg["symbol"].isin(symbols)]
    seen: dict[str, set[str]] = {}
    for r in hg.itertuples():
        names = [r.symbol, r.name]
        for col in (r.alias_symbol, r.alias_name, r.prev_symbol, r.prev_name):
            if isinstance(col, str):
                names += [x.strip('" ') for x in col.split("|")]
        for n in names:
            if isinstance(n, str) and len(normalise(n)) >= 3:
                seen.setdefault(normalise(n), set()).add(r.symbol)
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
