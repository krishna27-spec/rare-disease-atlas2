# Three video scripts, ready to read out

You can read these word for word. The left column is what to do on screen, the right column is what to say. Lines in *italics* are notes for you, not to be spoken.

## Before you record (once)

1. In a terminal, in the project folder: `uv run uvicorn src.atlas.server:app --port 8000`
2. Open **http://localhost:8000** in a **new browser window** (so the intro plays). Make the window large.
3. Start your screen recorder (OBS, Loom or Zoom) with the microphone on.
4. Read slowly. If you finish early, that is fine. If you run over, drop the line marked *(optional)*.

**How to say the hard words**

| Word | Say it like |
|---|---|
| Sanfilippo | san-fi-LIP-oh |
| gpt-oss | G-P-T, O-S-S |
| parquet | par-KAY |
| Reactome | ree-AK-tome |
| Batten | BAT-en |
| HGSNAT (only if you want to name the gene) | H-G-S-nat |

---

## Video 1: Demo (60 seconds)

*This one shows the product. No technical words.*

| Do this | Say this |
|---|---|
| The site opens and the intro animation plays. Wait for "Atlas AI" to appear, then click **Enter the Atlas**. | "This is Atlas AI. Maria's daughter has a rare disease called Sanfilippo C. There is no approved treatment, and Maria leads the patient group." |
| Click the search box. Type `sanfilipo c` (one p, on purpose). Press **Enter**. | "She types the name, even with a typo. Atlas finds the disease, its gene, and how common it is." |
| Click **Connections**. Wait three seconds while the map draws. Click the line between the centre and **MPS IIIA**. A panel opens on the right. Then press **Escape**. | "Who is like us? Sanfilippo A and B share the same biology. If I click any line, I see the source and the exact sentence it came from." |
| Click **Research**. Scroll down slowly to the three numbered steps. | "What already exists? Studies she can join, and three next steps for this week." |
| Click **Landscape**. Point at the row of circles, then scroll to the world map. | "Where does the disease stand? These are the milestones toward a treatment, the one still missing, and where studies are recruiting right now." |
| Click **Rare Disease Atlas** at the top left. Type `cystic fibrosis`. | "And when Atlas doesn't know a disease, it says so. Every link has a source. That is the whole idea." |

---

## Video 2: Tech (60 seconds)

*This one explains how it was built. Open the GitHub page of the repository in the browser before you start.*

| Do this | Say this |
|---|---|
| On the GitHub page, scroll to the diagram under **How it works**. | "Atlas is a knowledge graph. Python collects data from ten public databases and saves it as two small files. A FastAPI server reads those files, and the website is built in React. We drew the graph ourselves on a canvas." |
| Scroll to the table **Where gpt-oss is used, and how it is checked**. | "The part we care about most is how we use the language model. OpenAI's G-P-T O-S-S reads research papers and suggests facts. But we don't trust it blindly. Our code keeps a fact only if the quoted sentence is really in the paper. Then a second, larger model checks it again. That caught real mistakes." |
| Scroll to **What it does not do yet**. | "What went wrong: the free plan only gave us two hundred thousand tokens a day. So we read 120 of 712 papers, and the site says that openly." |
| *(optional)* Stay on the same section. | "We also tried a second biology source for scoring. It made the results worse, so we kept it for navigation only." |
| Switch to the site and click any **Why?** button so the evidence panel shows. | "What we learned: let the model suggest, and make the code verify. That is how we can show the source for everything." |

---

## Video 3: Team video (about 2 minutes)

*This one tells the whole story: the problem, what you built, and what comes next. You can be on camera for the first and last lines and show the screen in between.*

| Do this | Say this |
|---|---|
| On camera, or the intro animation playing. | "Hi, we are the team behind Atlas AI. We built it for the Hack-Nation challenge, AI Atlas for the World's Rare Diseases." |
| Stay on the intro, then click **Enter the Atlas**. | "There are around ten thousand rare diseases, and fewer than five percent have an approved treatment. When a family gets a diagnosis like that, they end up doing the research themselves. The information they need exists, but it is spread across many separate databases." |
| Search `sanfilippo c`, press Enter. Show the Overview. | "Atlas AI brings that information into one map. We started with 22 rare brain diseases. You type a disease, and you first get the basics: the gene, how common it is, and how it is inherited." |
| Click **Connections**. Let the map draw. Click **Expand connections** twice. | "Then the map shows what it is connected to. Related diseases, the biology they share, and the patient groups. We group diseases by how they work, not by their names." |
| Click any line on the map. The evidence panel opens. Close it with **Escape**. | "The rule we set for ourselves is simple. Nothing appears without evidence. Every line shows its source, the date, and when it came from a paper, the exact sentence." |
| Click **Research**, scroll to the next steps. | "For a patient group, the useful part is this. Which studies already exist, so they don't have to start from zero, and three concrete next steps." |
| Click **Landscape**. Show the milestones and the world map. | "We also added things the challenge did not ask for. The milestones on the road to a treatment, a world map of where studies run, and the reasons earlier trials stopped." |
| Click **Evidence** in the top bar. | "We used OpenAI's open models to read research papers. Our code checks every fact they suggest, and a second model reviews it. We are honest about the limits: only part of the papers have been read so far." |
| On camera, or back on the home page. | "With more time, we would read the rest, add more diseases, and let patient groups add their own. Thank you for watching." |

---

## If someone asks you a question afterwards

| Question | Short answer |
|---|---|
| What is a knowledge graph? | A list of things (diseases, genes, studies, people) and the facts that link them. |
| Where does the data come from? | Ten public databases, such as ClinicalTrials.gov, PubMed and Orphanet, plus the websites of patient groups. |
| Where is OpenAI used? | Their open model gpt-oss reads papers, reviews the facts, and writes the next steps in plain language. |
| How do you stop the model making things up? | A fact is kept only if its quoted sentence is really in the paper. A second model reviews it. Every next step must cite real facts. |
| Why only 22 diseases? | The brief says to start with a focused group. Adding a disease is one line in a file and a rebuild. |
| What does "10×" mean here? | Reusing studies that related diseases already built, instead of starting a new one from nothing. We show real study durations and claim no saving we can't cite. |
| What doesn't work yet? | Most papers are still unread, there is no phone layout, and it is not on a public web address. |
