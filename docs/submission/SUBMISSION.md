# Submission pack

Everything the submission form asks for, in the order of the guide.

| # | Item | Where it is |
|---|---|---|
| 1 | Short description | Below |
| 2 | Demo video (60 s) | Script below. Record, upload, paste the link in the form |
| 3 | Tech video (60 s) | Script below. Same |
| 4 | 1-page report | [`AtlasAI_OnePager.pdf`](AtlasAI_OnePager.pdf). The guide wants it named `TeamName_OnePager.pdf`, so rename it. To edit the text, change `onepager.html` and print it to PDF from a browser (A4, background graphics on). |
| 5 | GitHub repository | https://github.com/krishna27-spec/rare-disease-atlas2 |
| 6 | Zipped code | Run `git archive --format=zip -o AtlasAI_code.zip HEAD ":(exclude)data/cache" ":(exclude)docs/challenge-brief.pdf"` in the repo |
| 7 | Dataset | https://github.com/krishna27-spec/rare-disease-atlas2/tree/main/data (described in [`data/README.md`](../../data/README.md)) |

---

## 1. Short description (about 250 words)

**Atlas AI: a map of rare diseases where every line shows its source**

When a child is diagnosed with a rare disease that has no treatment, the parents become the research team. They know the gene's name. They don't know which other diseases work the same way, whether someone has already built a registry they could use, or who to call. That knowledge exists, but it sits in a dozen databases that don't talk to each other.

We built Atlas AI for those parents. It is a knowledge graph of 22 rare neurological diseases, joined from ten public sources into about 4,000 facts, with a website on top. You type a disease and get four answers: which diseases share its biology and why, what studies and registries already exist, which patient groups and researchers bridge them, and three concrete next steps.

What we're proudest of is that nothing on the screen is unsupported. Click any line on the map and you see where it came from, when, and the exact quoted sentence. OpenAI's gpt-oss reads the papers, but code throws away any fact whose quote isn't really in the abstract, and a second model reviews what's left. When the Atlas doesn't know something, it says so and tells you what was searched.

It runs today with one command and no API keys. Beyond the brief, each disease also gets a world map of study sites, the milestones still missing on the road to a treatment, and the sponsors' own reasons for why earlier trials stopped.

---

## 2. Demo video script (60 seconds)

Record the screen at 1440 × 900 or larger with the site running locally. Speak at a normal pace; the words below come to about 115, which leaves room to breathe. Before recording, open the site once in a new window so the intro plays.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:08 | The intro: DNA helix, the network growing, "Atlas AI" appears. Click **Enter the Atlas**. | "Maria's daughter has Sanfilippo C. There is no approved treatment, and Maria runs the patient group." |
| 0:08–0:15 | Type `sanfilipo c` (with the typo), press Enter. The Overview loads. | "She types the name, typo and all. Atlas finds the disease, its gene and how common it is." |
| 0:15–0:28 | Click **Connections**. Let the map draw itself. Click the line between MPS IIIC and MPS IIIA; the evidence drawer opens. Close it. | "Who is like us? Sanfilippo A and B share the same pathway. Click any line and you get the source and the exact sentence." |
| 0:28–0:37 | Click **Research**. Pause on the three study cards, scroll to the three next steps. | "What already exists? Natural history studies she can join, and three next steps for this week." |
| 0:37–0:50 | Click **Landscape**. Show the milestone row, scroll to the world map, hover a green point. | "Where does the disease stand? The milestones toward a treatment, the one still missing, and where studies are recruiting right now." |
| 0:50–1:00 | Click the logo, type `cystic fibrosis`. The "not in the Atlas yet" answer shows. | "And when Atlas doesn't know, it says so. Every link has a source. That's the whole idea." |

If you run long, cut the 0:28–0:37 block down to the study cards only.

---

## 3. Tech video script (60 seconds)

Talk over three things: the architecture diagram in the README, a few seconds of `src/extract.py` and `src/graph/check.py` in the editor, and the terminal running `uv run python -m src.graph.build`. About 135 words.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:13 | README, "How it works" diagram. | "Atlas is a knowledge graph in two parquet files. Python pulls from ten public databases, FastAPI serves it, and the site is React with the graph drawn by hand on canvas." |
| 0:13–0:32 | `src/extract.py`, the quote check; then `src/graph/review.py`. | "The part we care about most is the LLM. OpenAI's gpt-oss reads PubMed abstracts and proposes facts. Code keeps a fact only if the quoted sentence is really in the abstract, then a larger model reviews it. That caught real errors, like a gene attached to the wrong Batten subtype." |
| 0:32–0:52 | Terminal: the build finishing with "Graph check passed". Then `data/graph/STATS.md`. | "What went wrong: the free tier gave us two hundred thousand tokens a day, so we read 120 of 712 abstracts, and the site says so. Adding Gene Ontology to the similarity score also broke a cluster, so we use it for navigation only." |
| 0:52–1:00 | The site's evidence drawer. | "The lesson: let the model propose and make the code verify." |

---

## Notes before you submit

- The one-pager's "How we spent our time" section is taken from commit timestamps in the two repositories. Correct it if the real day went differently, and add anything that happened before the first commit.
- Team name and member names are not filled in anywhere. Add them to the one-pager and, if you want, to the README.
- The demo script assumes the site is running locally. If you deploy it before recording, record against the public URL instead.
