# UI Redesign Specification — AI Atlas for Rare Diseases

## 1. Project

Repository:

`https://github.com/Nothing4601/rare-disease-atlas`

Target branch:

`ui-redesign`

This specification is for the **frontend/UI/UX redesign phase** of the Rare Disease Atlas hackathon project.

The goal is to transform the existing working application into a polished, beautiful, biology-oriented, hackathon-ready product experience while preserving the existing backend and data functionality.

---

# 2. CRITICAL SCOPE RULE — BACKEND IS FROZEN

## DO NOT MODIFY THE BACKEND

This is the most important requirement in this document.

The existing backend/data layer is intentionally being kept unchanged because backend improvements will be handled later.

Treat the existing backend as a **black box**.

### Do NOT modify:

- Backend business logic
- ETL pipelines
- Data ingestion
- Data processing
- Graph-generation algorithms
- Graph construction logic
- Search/retrieval logic
- Ranking algorithms
- Recommendation logic
- LLM logic
- Backend API behavior
- Data schemas
- Database structures
- Existing datasets
- Graph-generation scripts
- Scientific computation
- Existing research/biology logic
- Existing backend Python modules unless absolutely required for an already-existing frontend integration

### You MAY modify:

- Frontend/UI code
- UI components
- CSS/styling
- Layout
- Typography
- Colors
- Spacing
- Navigation
- Frontend state handling
- Animations
- Transitions
- Loading states
- Empty states
- Error presentation
- Graph visualization styling
- Graph interaction presentation
- Icons
- Tooltips
- Search interface
- Entity detail panels
- Evidence presentation
- Research-opportunity presentation
- Landing/intro experience
- Responsive behavior
- Accessibility
- Frontend-only visual transformations of existing data

### Important rule

If you believe a UI feature requires changing the backend:

**STOP and ask me first.**

Do not silently modify the backend to make the UI easier to implement.

If an existing backend result is imperfect, present it clearly and elegantly rather than fixing the backend.

---

# 3. FIRST STEP — INSPECT BEFORE CODING

Before changing anything:

1. Inspect the repository.
2. Read the existing `CLAUDE.md`.
3. Identify the current application architecture.
4. Identify which files/components are responsible for presentation.
5. Determine how the current UI consumes the existing backend/data.
6. Run the application if possible.
7. Understand the current user flow.
8. Identify the minimum set of files required for the redesign.

Do NOT assume the project uses React, Next.js, Vue, Streamlit, etc.

Determine the actual architecture from the repository.

Do not rewrite the application into another framework unless I explicitly approve it.

Preserve working functionality.

---

# 4. PRODUCT VISION

The product is an:

**AI Atlas for the World's Rare Diseases**

The core idea is to connect scattered rare-disease knowledge and help users move from:

**Disease → Understanding → Connection → Evidence → Action**

The experience should make the graph feel like a scientific reasoning tool rather than merely a visualization.

The graph is the engine.

The UI should explain:

- Why a connection exists
- What evidence supports it
- How confident the connection is
- What is uncertain
- What contradictory evidence exists
- What the user can do next

The application should feel like a combination of:

- Biomedical research atlas
- Knowledge graph
- Scientific discovery interface
- Research intelligence tool
- Patient-oriented navigation system

It should NOT feel like:

- A generic SaaS dashboard
- A generic AI chatbot
- A cyberpunk interface
- A gaming UI
- An overly neon visualization
- A generic admin panel

---

# 5. TARGET USERS

The interface should support multiple personas without creating completely separate applications.

Important personas include:

### Patient organization leader

Needs to:

- Search a disease
- Understand biological mechanisms
- Find related diseases
- Find patient groups
- Find registries
- Find relevant studies
- Find potential collaborators
- Understand what evidence supports each connection

### Caregiver / patient-facing user

Needs:

- Clear summaries
- Low cognitive load
- Understandable terminology
- Clear uncertainty
- Concrete next steps

### Biotech / research scout

Needs:

- Mechanistic overlap
- Research assets
- Studies
- Researchers
- Publications
- Potential opportunities
- Evidence quality

### Researcher

Needs:

- Genes
- Variants
- Mechanisms
- Phenotypes
- Publications
- Studies
- Research assets
- Evidence
- Contradictions
- Related diseases

---

# 6. CORE UX PRINCIPLE

Use the following conceptual flow:

## SEARCH → UNDERSTAND → CONNECT → VERIFY → ACT

The UI should make this flow obvious.

### Search

One global search should allow users to search for things such as:

- Disease
- Gene
- Variant
- Symptom / phenotype
- Mechanism
- Study
- Researcher
- Patient organization

### Understand

After selecting an entity, immediately provide a concise explanation.

Do not overwhelm the user with every available piece of information.

### Connect

Show relevant relationships through the knowledge graph.

### Verify

Every important connection should expose:

- Relationship type
- Explanation
- Evidence
- Source
- Confidence / strength
- Contradictory evidence where applicable

### Act

End important exploration paths with a useful next action or research opportunity.

---

# 7. LANDING / INTRO EXPERIENCE

Create a premium biological introduction before the main atlas.

The intro should feel scientific, elegant, mysterious, and modern.

## Visual concept

A dark biological environment.

A DNA double helix slowly rotates.

A specific region/gene becomes highlighted.

A subtle genetic variant/mutation is represented.

The biological signal expands outward into:

- Molecular relationships
- Pathways
- Mechanisms
- Phenotypes
- Related diseases
- Research studies
- Patient groups

The network gradually evolves into the knowledge graph.

The final visual state should transition naturally into the actual Atlas interface.

## Desired duration

Approximately 6–7 seconds for the main animation sequence.

However:

**Do NOT automatically force the user into the application after the animation.**

The animation should continue/loop subtly or remain in a final state until the user clicks.

Provide a clear action such as:

**Enter Atlas**

or

**Explore Atlas**

Also provide a subtle skip/enter option if appropriate.

## Important

The animation should not feel like:

- Explosions
- Sci-fi combat
- Cyberpunk
- Gaming
- Excessive neon

It should feel like:

- Biomedical
- Scientific
- Precise
- Elegant
- Premium
- Intelligent

If a heavy video asset would hurt performance, prefer an optimized CSS/WebGL/canvas/frontend animation where practical.

Do not add unnecessarily huge assets.

---

# 8. MAIN VISUAL IDENTITY

Use a dark biological aesthetic.

## Primary colors

### Background

`#08070D`

### Secondary background

`#0D0A15`

### Elevated surface

`#171321`

### Deep purple

`#6D3BFF`

### Main purple

`#8B5CF6`

### Lavender

`#A78BFA`

### Primary text

`#F5F3FA`

### Secondary text

`#B8B3C7`

### Muted text

`#777184`

## Semantic colors

Use semantic colors carefully.

### Confirmed / strong evidence

Green

### Uncertainty

Amber

### Contradiction

Red

### Neutral research / informational

Muted cyan

Do not let semantic colors replace the main purple brand language.

---

# 9. COLOR DISTRIBUTION

Approximately:

- 70% dark neutral surfaces
- 20% purple brand / interaction language
- 10% semantic accent colors

Avoid:

- Rainbow gradients
- Excessive neon
- Huge purple backgrounds
- Purple text everywhere
- Excessive glow
- Excessive glassmorphism

Purple should communicate:

- Interaction
- Focus
- Navigation
- Scientific discovery
- Brand identity

Semantic colors should communicate meaning.

---

# 10. BIOLOGY-ORIENTED VISUAL LANGUAGE

Biology should be part of the information design, not merely decoration.

Use consistent visual representations for graph entities.

Possible visual language:

### Gene

DNA-inspired node/glyph.

### Variant

Subtle altered DNA/base-pair representation.

### Mechanism

Pathway / molecular relationship symbol.

### Disease

Cell-like or biological entity symbol.

### Phenotype

Clinical / symptom-oriented indicator.

### Publication

Paper/document symbol.

### Study

Research/clinical-study symbol.

### Research asset

Experimental/infrastructure symbol.

### Patient group

Community/network symbol.

### Researcher

Person/network symbol.

### Clinical study

Clinical/research symbol.

Use a consistent icon system.

Do not simply use DNA emoji everywhere.

The biological styling should feel sophisticated and restrained.

---

# 11. MAIN ATLAS EXPERIENCE

The central experience should be the knowledge graph.

A suggested layout:

```text
┌───────────────────────────────────────────────────────────┐
│ Header / Global Search                                    │
├───────────────┬───────────────────────────────┬───────────┤
│               │                               │           │
│ Navigation /  │                               │ Selected  │
│ Filters       │       Knowledge Graph         │ Entity /  │
│               │                               │ Context   │
│               │                               │ Panel     │
│               │                               │           │
├───────────────┴───────────────────────────────┴───────────┤
│ Context / Evidence / Research Opportunity / Next Action   │
└───────────────────────────────────────────────────────────┘
```

Do not follow this layout rigidly if the existing architecture suggests a better solution.

The important principles are:

- Graph remains central
- Context is easy to access
- Information appears progressively
- The interface does not become cluttered

---

# 12. GLOBAL SEARCH

Create a strong global search experience.

Search should feel like the main gateway into the Atlas.

It should support searches for:

- Disease
- Gene
- Symptom
- Phenotype
- Mechanism
- Variant
- Study
- Researcher
- Patient group

Use:

- Clear search affordance
- Keyboard-friendly interaction
- Good focus states
- Useful empty state
- Loading state
- Search suggestions if existing data allows
- Entity-type indicators

Do not modify the underlying search implementation.

Only improve its presentation and interaction.

---

# 13. KNOWLEDGE GRAPH UX

The graph should feel alive but remain scientifically readable.

## Node design

Nodes should have:

- Clear hierarchy
- Entity-specific iconography
- Meaningful labels
- Hover state
- Selected state
- Relationship awareness

Avoid turning the graph into visual noise.

## Animation

Use subtle:

- Node transitions
- Edge highlighting
- Focus transitions
- Zoom transitions
- Selection transitions
- Hover effects

Avoid:

- Constant movement
- Excessive particle effects
- Distracting physics
- Unnecessary animations

The graph should feel responsive, not chaotic.

---

# 14. GRAPH INTERACTION

When a node is selected:

1. Highlight it.
2. Visually emphasize directly related nodes.
3. Reduce emphasis on unrelated nodes.
4. Open the entity context panel.
5. Provide a concise summary.
6. Allow deeper exploration.

When an edge is selected:

Show:

### Why is this connected?

Then provide:

- Relationship type
- Explanation
- Supporting evidence
- Source
- Confidence / strength
- Contradictory evidence if available

This is extremely important for the challenge.

The graph should never feel like:

> "These two things are connected because the UI says so."

The user should understand **why**.

---

# 15. ENTITY DETAIL PANEL

Create a polished right-side entity panel.

Suggested structure:

### Header

Entity name

Entity type

Small biological icon

### Summary

2–4 sentence concise explanation.

### Key facts

Show only useful high-signal information.

### Relationships

Relevant connected entities.

### Evidence

Supporting sources and evidence.

### Confidence

Clearly communicate strength/uncertainty.

### Contradictions

If contradictory findings exist, surface them clearly.

### Actions

Possible next exploration actions.

Use progressive disclosure.

Do not display everything simultaneously.

---

# 16. EVIDENCE PRESENTATION

Trust is a major part of the product.

The UI must distinguish between:

- Observed evidence
- Inferred relationships
- Uncertain connections
- Contradictory findings

Make this visually obvious.

For important relationships show:

**Relationship**

**Why it matters**

**Evidence**

**Source**

**Confidence**

**Contradictory evidence**

Do not invent evidence.

Do not invent scientific explanations.

Use only the information already supplied by the existing backend/data.

---

# 17. RESEARCH OPPORTUNITY / NEXT ACTION

The experience should eventually answer:

> "What can I do with this information?"

Create a visually strong research/action section where existing data supports it.

Possible sections:

- Research opportunity
- Shared mechanism
- Related patient community
- Existing registry
- Relevant study
- Relevant researcher
- Research asset
- Suggested next step
- Why this is relevant
- Evidence
- Uncertainty

The interface should move the user from:

**Discovery → Decision → Action**

Do not fabricate recommendations.

If the backend does not provide a meaningful route, clearly communicate:

- No supported route found
- What is missing
- What question could be investigated next

This is preferable to inventing a result.

---

# 18. PROGRESSIVE REVEAL

Follow the principle:

**Summary first. Depth on demand.**

Do not expose all information at once.

For example:

First:

> "This disease shares a mechanism with X."

Then allow:

> "Why?"

Then:

> Evidence

Then:

> Source

Then:

> Contradictory findings

This keeps the interface approachable while still serving expert users.

---

# 19. MICROINTERACTIONS

Use polished but restrained interactions:

- Smooth hover states
- Subtle focus rings
- Soft panel transitions
- Graph zoom transitions
- Search result animations
- Selection transitions
- Expand/collapse animations
- Loading skeletons
- Smooth navigation
- Button feedback

Keep animation durations short and purposeful.

Avoid animation for animation's sake.

---

# 20. TYPOGRAPHY

Use a modern, highly readable type system.

Prioritize:

- Clear hierarchy
- Strong headings
- Compact metadata
- Readable scientific text
- Good line height
- Good contrast

Avoid excessive futuristic fonts.

The product should feel like a serious scientific tool.

---

# 21. RESPONSIVENESS

The interface should remain usable at:

- Desktop
- Laptop
- Tablet where practical

Prioritize desktop because the graph/research workflow is the main experience.

Do not sacrifice graph usability for mobile optimization.

---

# 22. ACCESSIBILITY

Maintain:

- Strong text contrast
- Visible focus states
- Keyboard navigation where practical
- Meaningful button labels
- Semantic structure
- Non-color-only communication of evidence states

Important:

Color should carry meaning, but meaning should not depend ONLY on color.

Use icons, labels, or patterns where appropriate.

---

# 23. PERFORMANCE

Do not sacrifice application performance for visual effects.

Avoid:

- Huge video files
- Huge image assets
- Unnecessary dependencies
- Excessive DOM complexity
- Continuous expensive animations
- Excessive graph rendering effects

Prefer:

- CSS animations
- Lightweight SVG
- Existing graph rendering infrastructure
- Optimized assets
- Lazy loading where appropriate

---

# 24. PRESERVE EXISTING FUNCTIONALITY

The redesign must not remove existing working features.

Before changing something, understand what it currently does.

The goal is:

**Same underlying functionality + significantly better experience.**

Do not rewrite working backend functionality simply because it is not aesthetically ideal.

---

# 25. SCIENTIFIC INTEGRITY

This is a biomedical application.

Do not invent:

- Diseases
- Genes
- Variants
- Mechanisms
- Studies
- Publications
- Researchers
- Patient organizations
- Evidence
- Scientific relationships

Do not modify scientific data merely to make the demo look better.

If data is missing:

Present the absence clearly.

Example:

> No supported connection found

rather than inventing one.

---

# 26. HACKATHON DEMO QUALITY

The final UI should feel impressive within the first 30 seconds.

The ideal demo flow:

1. Landing animation
2. Enter Atlas
3. Search for a rare disease
4. Disease becomes the central graph node
5. Related biological relationships appear
6. Select a meaningful connection
7. "Why is this connected?" appears
8. Evidence/source is shown
9. Explore related disease / mechanism / study / patient group
10. Arrive at a research opportunity / next action

The experience should communicate the product's value without requiring a long explanation.

---

# 27. BRAND / PRODUCT FEEL

Possible visual/product direction:

**NEXUS — Rare Disease Atlas**

Possible tagline:

**Connect the science. Find the path forward.**

These are suggestions, not mandatory branding.

If the existing project already has a stronger name/identity, preserve it unless I explicitly request a rename.

---

# 28. IMPLEMENTATION STRATEGY

Work incrementally.

### Phase 1 — Understand

- Inspect architecture
- Run application
- Identify current UI
- Identify frontend boundaries

### Phase 2 — Foundation

- Establish visual system
- Background
- Typography
- Colors
- Spacing
- Cards/panels
- Buttons
- Inputs
- Icons

### Phase 3 — Landing

- Biology animation
- Entry interaction
- Transition into Atlas

### Phase 4 — Main Atlas

- Search
- Navigation
- Graph
- Entity panel

### Phase 5 — Evidence

- Relationship explanation
- Evidence
- Confidence
- Contradictions

### Phase 6 — Action

- Research opportunity
- Next step
- Related resources

### Phase 7 — Polish

- Transitions
- Loading states
- Empty states
- Error states
- Responsive behavior
- Accessibility
- Performance

---

# 29. IMPORTANT DECISION RULE

For every design decision ask:

> Does this help the user understand the biological knowledge graph and move toward a useful next action?

If yes, keep it.

If it is only decorative, reconsider it.

The UI should prioritize:

**Signal > Decoration**

---

# 30. GIT / BRANCH RULES

Work ONLY on:

`ui-redesign`

Do NOT push UI work to:

`main`

Before committing:

1. Run `git status`.
2. Review `git diff`.
3. Verify backend/data files have not been modified unintentionally.
4. Verify only intended UI/frontend files changed.
5. Test the application.
6. Fix UI issues.
7. Commit the changes.
8. Push to `ui-redesign`.

Suggested commit message:

`feat: redesign rare disease atlas UI`

If backend files are modified unintentionally:

**STOP. Do not commit. Ask me first.**

---

# 31. FINAL VERIFICATION CHECKLIST

Before considering the task complete, verify:

## Scope

- [ ] Backend unchanged
- [ ] Data unchanged
- [ ] ETL unchanged
- [ ] Graph-generation logic unchanged
- [ ] LLM/backend logic unchanged
- [ ] No scientific data fabricated

## UI

- [ ] Landing experience implemented
- [ ] Biology-oriented visual language implemented
- [ ] Purple/black visual identity implemented
- [ ] Global search polished
- [ ] Graph presentation polished
- [ ] Entity panel polished
- [ ] Evidence presentation polished
- [ ] Relationship explanation implemented
- [ ] Research/action section improved
- [ ] Loading states improved
- [ ] Empty states improved
- [ ] Error states improved
- [ ] Responsive behavior checked
- [ ] Accessibility considered
- [ ] Performance checked

## UX

- [ ] Search → Understand → Connect → Verify → Act flow is clear
- [ ] Progressive disclosure is used
- [ ] Graph is visually understandable
- [ ] Important connections explain WHY
- [ ] Evidence is easy to find
- [ ] Uncertainty is clearly communicated
- [ ] User can reach a useful next action

## Git

- [ ] Changes are on `ui-redesign`
- [ ] `main` was not modified
- [ ] Diff reviewed
- [ ] Backend files not unintentionally modified
- [ ] Commit created
- [ ] Changes pushed to `ui-redesign`

---

# 32. MOST IMPORTANT INSTRUCTION

Build a **beautiful, polished, biology-oriented frontend experience around the existing system**.

Do not rebuild the backend.

Do not modify scientific logic.

Do not fabricate data.

Do not assume architecture.

Inspect first.

Preserve functionality.

Improve the experience.

And if an important UI requirement genuinely requires a backend change:

**STOP AND ASK ME BEFORE TOUCHING THE BACKEND.**
