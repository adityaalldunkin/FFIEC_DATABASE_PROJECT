# Lenni Borrower AI — Expert Interview Sheet

**Purpose:** Capture how Lenni’s borrower-facing AI should respond when real Texas borrowers ask questions during a conversational loan intake. Your boss and colleague will role-play: one person asks as the **borrower**, the other answers as the **Lenni expert** (the answer the AI should give). Record every answer in the structured format below so any LLM can be trained, prompted, or evaluated against the same ground truth.

**Output files after the interview:**
- `borrower_llm_interview_answers.yaml` — one entry per question (filled in during the session)
- Optional: `borrower_llm_interview_notes.md` — free-form context that did not fit the YAML fields

**Related repo assets (for reference during the interview):**
- `content/loan_products.yaml` — product definitions, prep lists, how-to-approach scripts
- `content/borrower_scenarios.yaml` — realistic deal stories
- `match_deal.py` — listing → loan product + bank ranker (AI must not invent banks)

---

## How to run the interview (60–90 minutes)

### Roles
| Role | Responsibility |
|------|----------------|
| **Borrower** | Ask questions naturally, as if chatting with Lenni. Use a persona (see below). Push back, ask follow-ups, say “I don’t know” sometimes. |
| **Lenni expert** | Answer what the AI **should** say: accurate, plainspoken, Texas community-bank appropriate. Say when the AI should **ask a question back** instead of answering. |
| **Recorder** | Same person or third person — copy answers into YAML as you go. |

### Suggested personas (pick 2–3 per session)
1. **Experienced multifamily operator** — Dallas value-add bridge, 40+ units  
2. **First-time land buyer** — raw acreage near a small Texas town, unsure of loan type  
3. **Owner-operator manufacturer** — buying the building their business occupies (Waco-style)  
4. **Industrial investor** — refinance / cash-out on NNN warehouse (Houston-style)  
5. **Growing business owner** — working capital line, asset-light (Austin SaaS-style)  
6. **Skeptical first-time CRE borrower** — “Why not just call one bank?”

### Rules for expert answers
- **Never** promise rates, approvals, or specific bank appetite — FFIEC data shows portfolio mix, not credit policy.  
- **Always** distinguish: (a) general education, (b) what Lenni can recommend from data, (c) what only a banker can confirm.  
- When information is missing, the AI should **ask one clear follow-up question**, not guess.  
- Bank names in answers should only appear when tied to **public portfolio data** or **explicit “example shortlist”** language — not as guarantees.

---

## Answer recording format (required)

Copy this block for **each question** you complete. Save all blocks in a single file:  
`ONLY_TEXAS_SINCE_2025/content/borrower_llm_interview_answers.yaml`

```yaml
# ─── Repeat this block per question ───
- id: "Q-###"                    # Must match question ID in this sheet
  question_text: ""              # Exact words the borrower asked (verbatim)
  borrower_persona: ""           # e.g. multifamily_operator | land_first_time | owner_occupied | ci_business | skeptical_new
  interview_date: "YYYY-MM-DD"
  answered_by: ""                # Name or role of Lenni expert

  answer:
  # --- Core response (what the user sees) ---
    user_facing_reply: |         # 2–6 sentences. Plain English. No jargon unless defined.
      ""

    tone: ""                     # One of: reassuring | direct | educational | cautionary | encouraging

  # --- Behavior (what the AI should DO, not only say) ---
    response_type: ""            # One of: answer_only | answer_and_ask | ask_only | defer_to_human | show_disclaimer

    follow_up_questions:         # Questions the AI should ask NEXT (0–3). Empty if answer_only.
      - ""

    slots_to_extract:            # Deal fields this turn should fill or update (match chatbot state)
      - ""                       # e.g. intent, parent_key, metro, price_n, units, acres, occupancy_pct, timeline, sponsor_experience

  # --- Factual grounding ---
    loan_product_keys:           # From loan_products.yaml parent keys: mf | inv | own | con | ci | res | oth
      - ""

    loan_subtype_slugs:          # Optional slugs e.g. bridge, acquisition, lot-loans
      - ""

    bank_matching_signals:       # How FFIEC / Lenni data should influence recommendations (not bank names unless examples)
      - ""

    documents_to_mention:        # What borrower should gather (from what_to_prepare when possible)
      - ""

  # --- Safety & compliance ---
    must_say_disclaimer: false   # true if reply touches rates, approval odds, or bank willingness
    disclaimer_text: |           # Required if must_say_disclaimer is true; else empty string
      ""

    must_not_say:                # Hard guardrails — things the AI must never claim
      - ""

  # --- Quality metadata (for LLM training / eval) ---
    confidence: ""               # high | medium | low — expert’s confidence this answer is correct for Lenni
    source_notes: |              # Where this came from: experience, Call Report logic, scenario YAML, etc.
      ""

    example_borrower_phrases:    # Alternate ways borrowers might ask the same thing
      - ""

    tags:                        # Free tags for search/filter
      - ""
# ─── End block ───
```

### Minimal example (filled in)

```yaml
- id: "Q-012"
  question_text: "I found a 12-acre lot outside Brenham. Do I need a construction loan or a land loan?"
  borrower_persona: land_first_time
  interview_date: "2026-06-25"
  answered_by: "Doak"

  answer:
    user_facing_reply: |
      For raw land you’re holding — not building on yet — banks usually start with a land or lot loan,
      not a construction loan. Construction is for when you’re ready to build soon with plans and a budget.
      What’s your plan: hold the land, develop lots, or build something on it? And do you have a purchase price in mind?
    tone: educational

    response_type: answer_and_ask
    follow_up_questions:
      - "Are you planning to hold, develop, or build on the land?"
      - "What city or county is the property in?"
      - "What’s the asking price or your target purchase price?"
    slots_to_extract:
      - intent
      - parent_key
      - acres
      - city
      - metro
      - price_n

    loan_product_keys:
      - con
    loan_subtype_slugs:
      - lot-loans
      - land-development

    bank_matching_signals:
      - "Rank banks with construction + land portfolio share in College Station / Bryan metro"
      - "Ag/farmland mix relevant if property is rural acreage"

    documents_to_mention:
      - Purchase contract or LOI
      - Survey and title commitment
      - Brief written plan (hold vs develop vs build)

    must_say_disclaimer: false
    disclaimer_text: ""
    must_not_say:
      - "You will definitely get a land loan"
      - "Any specific rate or LTV"

    confidence: high
    source_notes: "Aligned with loan_products.yaml construction/land subtypes and match_deal intent=hold vs develop."
    example_borrower_phrases:
      - "Is this a lot loan or construction?"
      - "I'm not building yet — just buying acreage"
    tags:
      - land
      - product_selection
      - intent_discovery
```

---

## Section A — Opening & trust (borrower → AI)

| ID | Borrower question (read aloud or paraphrase naturally) | Why it matters for the AI |
|----|----------------------------------------------------------|---------------------------|
| **Q-001** | What is Lenni? Are you a bank? | Sets scope; AI must not impersonate a lender. |
| **Q-002** | Can you approve my loan or give me a rate? | Compliance boundary; disclaimer behavior. |
| **Q-003** | How do you know which banks to recommend? | Explain FFIEC Call Report / portfolio mix without overclaiming. |
| **Q-004** | Is my information private? Who sees this conversation? | Trust; aligns with Lenni “private by design” positioning. |
| **Q-005** | I’m not a banker — can you explain this in plain English? | Tone calibration for all future answers. |
| **Q-006** | Why should I use this instead of calling my realtor’s favorite lender? | Value prop: specialist targeting, preparation, shortlist logic. |
| **Q-007** | Does this cost me anything as a borrower? | Business model clarity (if known); avoid making up fees. |
| **Q-008** | I’m only looking in Texas — is that a problem? | Geographic scope; matches current data coverage. |

---

## Section B — “What loan do I need?” (product discovery)

| ID | Borrower question | Why it matters |
|----|-------------------|----------------|
| **Q-010** | I want to buy a property — what kind of loan do I need? | Core intent + property type disambiguation. |
| **Q-011** | What’s the difference between a bridge loan and a regular commercial loan? | Product education; when to ask follow-ups. |
| **Q-012** | I found a 12-acre lot outside Brenham. Do I need a construction loan or a land loan? | Land vs construction (see example above). |
| **Q-013** | I’m buying a 40-unit apartment building to renovate. What loan is that? | MF value-add / bridge vs acquisition. |
| **Q-014** | I own a warehouse and want to refinance and pull cash out. What should I ask for? | Investor CRE refinance subtype. |
| **Q-015** | I want to buy the building my business operates out of. Is that the same as an investment property loan? | Owner-occupied vs investor CRE. |
| **Q-016** | My company needs a line of credit for payroll — is that a real estate loan? | C&I vs CRE routing. |
| **Q-017** | I’m looking at farmland/ranch land — do Texas community banks do that? | Ag/farmland (`oth` parent key). |
| **Q-018** | I’m buying a duplex — is that multifamily? | 1–4 residential vs 5+ MF threshold. |
| **Q-019** | I have a listing URL — can you tell me what loan fits? | URL / paste intake behavior. |
| **Q-020** | I don’t know what I don’t know — where do I start? | Opening script for conversational intake. |

---

## Section C — Deal facts the AI must collect (borrower may ask OR expert defines what AI should ask)

*For these, the borrower may ask “what do you need from me?” — record both the borrower-facing answer and the slots the AI must extract.*

| ID | Borrower question | Slots / notes |
|----|-------------------|---------------|
| **Q-030** | What information do you need from me to figure this out? | Master intake checklist by product family. |
| **Q-031** | Does the purchase price matter if I’m not sure yet? | `price_n` optional vs required; ranges OK? |
| **Q-032** | I’m under LOI — is that enough to start talking to banks? | LOI vs contract; prep list. |
| **Q-033** | How many units does the property have to be “multifamily”? | 5+ units rule. |
| **Q-034** | What if occupancy is only 70%? Does that change the loan type? | Value-add / bridge signals. |
| **Q-035** | I want to close in 30 days — is that realistic? | Timeline; bridge vs perm expectations. |
| **Q-036** | I’ve never done a commercial deal before — does that matter? | `sponsor_experience`; bank selection nuance. |
| **Q-037** | How much of my own money do I need to put in? | Equity / LTV — educate, don’t quote bank terms. |
| **Q-038** | The property is in a small town — does Dallas bank still lend there? | Metro vs statewide lending; HQ vs footprint. |
| **Q-039** | Can I do this with an LLC or does it have to be personal? | Entity structure — defer specifics to bank. |

---

## Section D — Bank selection (borrower → AI)

| ID | Borrower question | Why it matters |
|----|-------------------|----------------|
| **Q-040** | Which banks should I talk to for this deal? | Core `rank_banks` output; explain *why* each bank. |
| **Q-041** | Why did you recommend [Bank X]? | Explain portfolio % / specialist logic. |
| **Q-042** | Should I only talk to banks in my city? | HQ city vs statewide; metro filter behavior. |
| **Q-043** | Are bigger banks or community banks better for my deal? | ICP ($500M–$2B) framing when appropriate. |
| **Q-044** | How many banks should I contact? | Scenario guidance (e.g. 8–10 MF, 10–15 investor CRE). |
| **Q-045** | This bank isn’t on your list — should I ignore them? | Limits of FFIEC data; not exhaustive. |
| **Q-046** | Do you know if [Bank X] does bridge loans? | Must not claim credit policy — portfolio proxy only. |
| **Q-047** | Can you give me the loan officer’s name? | Boundary: website / public info only vs fabrication. |
| **Q-048** | I already bank with [Bank Y] — should I start there? | Relationship banking advice tone. |

---

## Section E — How to approach banks (borrower → AI)

| ID | Borrower question | Why it matters |
|----|-------------------|----------------|
| **Q-050** | What do I say on the first call to a bank? | `how_to_approach.opening` templates. |
| **Q-051** | What questions should I ask the banker? | Per-product `questions` from YAML. |
| **Q-052** | What documents should I have ready before I call? | `what_to_prepare` lists. |
| **Q-053** | Should I ask for a rate on the first call? | Process coaching — Lenni voice. |
| **Q-054** | How do I send a “deal summary” — what goes in it? | One-pager structure for community banks. |
| **Q-055** | They asked for a rent roll — what is that? | Glossary / education layer. |
| **Q-056** | What’s NOI and why do banks care? | CRE literacy without condescension. |
| **Q-057** | How long does bank approval usually take? | Ranges + “every bank differs” disclaimer. |
| **Q-058** | Can I talk to multiple banks at once? | Parallel process etiquette. |
| **Q-059** | The banker went quiet — what should I do? | Relationship follow-up coaching. |

---

## Section F — Anxiety, mistakes & edge cases

| ID | Borrower question | Why it matters |
|----|-------------------|----------------|
| **Q-060** | I’m worried my deal is too small for a bank. | Deal size vs median Texas bank loan book. |
| **Q-061** | I was told banks don’t lend on land anymore — is that true? | Accurate nuance; specialist banks exist. |
| **Q-062** | My credit isn’t perfect — should I even bother? | When to defer to banker; no false hope. |
| **Q-063** | What if the AI gets my deal wrong? | Correction flow; human handoff. |
| **Q-064** | Can you guarantee I’ll get funded? | Hard refusal + disclaimer template. |
| **Q-065** | I changed my mind — I want to refinance instead of buy. | Session state update / intent change. |
| **Q-066** | Actually it’s two properties — does that change things? | Multi-asset complexity boundary. |
| **Q-067** | I’m looking at a property in Houston but I live in Dallas. | Sponsor location vs property location. |
| **Q-068** | The seller is offering owner financing — how does that interact with a bank loan? | Out of scope vs educational pointer. |

---

## Section G — End of conversation (“loan package” output)

| ID | Borrower question | Why it matters |
|----|-------------------|----------------|
| **Q-070** | Can you summarize everything and tell me my next steps? | Roadmap / `build_roadmap` style output. |
| **Q-071** | Can you give me a checklist I can print? | `what_to_prepare` + steps 1–4. |
| **Q-072** | Can you write the email I should send to the first bank? | Templated outreach; no invented terms. |
| **Q-073** | What loan product page should I read on the Lenni site? | Link to `loan-types/...` URLs. |
| **Q-074** | Save my deal — can I come back later? | Session persistence expectation (product decision). |
| **Q-075** | Connect me to a real person at Lenni / a bank. | Handoff rules for V1 vs future. |

---

## Section H — Persona-specific deep dives (optional second session)

Use these after Sections A–G. Same YAML format; tag `borrower_persona` accordingly.

| ID | Persona | Borrower question |
|----|---------|-------------------|
| **Q-080** | Multifamily operator | "I have a value-add business plan but no stabilized NOI yet — who funds that?" |
| **Q-081** | Multifamily operator | "What's mini-perm vs bridge vs agency takeout?" |
| **Q-082** | Land / first-time | "I might subdivide in 3 years — what loan do I get now?" |
| **Q-083** | Owner-occupied | "Will the bank look at my business financials or just the building?" |
| **Q-084** | C&I / SaaS | "We don't have much collateral — can a community bank still do a line?" |
| **Q-085** | Industrial investor | "Single-tenant NNN — what DSCR will they ask about?" |
| **Q-086** | Skeptical new | "This feels like ChatGPT — why should I trust your bank list?" |
| **Q-087** | Experienced sponsor | "Skip the basics — here's my deal memo [paste]. Rank banks." |
| **Q-088** | Ag / ranch | "Is this farmland lending or land development?" |

---

## Interview scorecard (fill after session)

```yaml
interview_session:
  date: "YYYY-MM-DD"
  participants:
    borrower_role: ""
    expert_role: ""
    recorder: ""
  personas_used: []
  questions_completed: []    # List of Q-IDs answered
  questions_skipped: []
  gaps_identified:           # Topics we still don't know how to answer
    - ""
  priority_additions:        # New questions to add to this sheet
    - ""
```

---

## After the interview — how this feeds any LLM

| Use | How |
|-----|-----|
| **System prompt / RAG** | Load `borrower_llm_interview_answers.yaml` as few-shot examples or retrieval chunks tagged by `tags` and `loan_product_keys`. |
| **Eval suite** | For each `id`, run candidate models with `question_text` + persona; compare output to `user_facing_reply`, `follow_up_questions`, `must_not_say`. |
| **Slot extraction training** | Pair `question_text` → `slots_to_extract` ground truth for fine-tuning or regression tests. |
| **Guardrails** | Aggregate all `must_not_say` and `disclaimer_text` into a shared policy block for any model provider. |

---

## Quick reference — `slots_to_extract` vocabulary

Use these exact keys when filling YAML (matches planned chatbot state + `match_deal.py`):

| Slot | Description |
|------|-------------|
| `intent` | hold \| develop \| build \| value_add \| bridge \| refinance \| owner_occupy \| acquire |
| `parent_key` | mf \| inv \| own \| con \| ci \| res \| oth |
| `property_type` | Human label e.g. "Multifamily", "Land / lot" |
| `city` | City name |
| `metro` | Texas metro bucket e.g. "Dallas–Fort Worth" |
| `price_n` | Numeric price / loan amount |
| `units` | Unit count (5+ for MF) |
| `acres` | Land acreage |
| `occupancy_pct` | Current occupancy if applicable |
| `timeline` | Close / project timeline |
| `sponsor_experience` | none \| some \| experienced |
| `equity_available` | Borrower liquidity / down payment (qualitative or numeric) |
| `use_of_funds` | Cash-out, working capital, construction budget, etc. |

---

*Document version: 2026-06-25 · Lenni borrower AI knowledge capture*
