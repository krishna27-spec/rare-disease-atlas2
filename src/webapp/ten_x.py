"""The 10x tab: one milestone, starting a natural history study for MPS IIIC, usual route vs Atlas route.

No invented numbers: durations come from real ClinicalTrials.gov records (data/graph/nhs_timelines.csv) and the
only general claim is quoted from FDA guidance."""
import pandas as pd
import streamlit as st

from src.webapp.data import GRAPH

FDA = "https://www.fda.gov/media/122425/download"
MPS3C = "MONDO:0009657"


def render(G, disease: str) -> None:
    st.markdown("### 10× idea: start a natural history study for MPS IIIC without starting from zero")
    st.caption("Milestone: a family group wants a natural history study (a study that records how the disease "
               "progresses without treatment), the evidence regulators ask for before trials.")
    tl = pd.read_csv(GRAPH / "nhs_timelines.csv")
    done = tl[(tl.status == "COMPLETED") & tl.months.notna()]
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Usual route: build it from scratch")
        st.markdown(f"- FDA draft guidance says prospective natural history studies generally take more time than "
                    f"reusing existing data, and longitudinal ones can be lengthy and costly ([FDA, 2019]({FDA})).")
        st.markdown(f"- **How long do such studies run?** Of the {len(tl)} Sanfilippo natural history studies in "
                    f"ClinicalTrials.gov, {len(done)} are completed: median **{done.months.median():.0f} months**, "
                    f"range {done.months.min():.0f} to {done.months.max():.0f} months, median enrolment "
                    f"{done.enrollment.median():.0f} children.")
        st.markdown("- We could not find a published figure for the time to *set up* a study (protocol, ethics approval, "
                    "sites, funding), so we do not state one.")
    with c2:
        st.markdown("#### Atlas route: reuse what sister diseases already built")
        sib = tl[tl.disease.str.contains("IIIA|IIIB|IIID")]
        own = tl[tl.disease.str.contains("IIIC")]
        st.markdown(f"- The graph shows **{len(sib)}** natural history studies for MPS IIIA, IIIB and IIID: protocols, "
                    "outcome measures and teams to learn from, and ask to collaborate with.")
        st.markdown(f"- **MPS IIIC already has {len(own)} registered:** check these first. Joining may beat starting a new one.")
        for r in own.itertuples():
            st.markdown(f"    - [{r.nct}]({r.source_url}) {r.title} · {r.status} · {r.start} to {r.completion} · {r.sponsor}")
        st.markdown("- Next step: contact the study teams below (see *What to do next* for cited leads).")
    st.markdown("#### Existing Sanfilippo natural history studies (ClinicalTrials.gov)")
    show = tl[["nct", "disease", "title", "status", "start", "completion", "months", "enrollment", "sponsor"]]
    st.dataframe(show, hide_index=True, width='stretch')
    st.caption(f"Retrieved {tl.retrieved.iloc[0]}. Duration = registered start to registered (planned or actual) completion.")
    st.markdown("#### Assumptions")
    st.markdown("- A study for MPS IIIC could reuse outcome measures from MPS IIIA/IIIB. *Not yet validated:* it needs "
                "clinicians to confirm the diseases are close enough (they share the heparan sulfate degradation "
                "pathway, but have different genes).\n"
                "- Durations are those of the registered studies; a new study could be shorter or longer.\n"
                "- We state no time or cost saving, because we have no cited figure for one.")
    st.markdown("#### What must be validated next")
    st.markdown("1. Whether each existing MPS IIIC study is still enrolling and open to this family.\n"
                "2. Whether sister-disease protocols and registries can be shared (ask the sponsors).\n"
                "3. Expert review of how well outcome measures transfer between subtypes.")
