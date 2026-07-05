# Lenni Borrower Chat — Build Session

**Date:** July 5, 2026  
**Goal:** Build a conversational loan advisory chat interface using open-weight LLM architecture (with rules fallback), integrated with the existing `match_deal` engine.

---

## What was built

### Architecture (hybrid — per research doc)

```
Borrower UI (chat.html)
    ↓ POST /api/chat
chat_engine.py          ← orchestrator (state machine)
    ├── llm_client.py   ← Ollama | OpenAI | rules fallback
    ├── chat_state.py   ← slot tracking + question priority
    ├── knowledge_rag.py← RAG over loan_products.yaml + scenarios
    ├── guardrails.py   ← input/output safety
    └── match_deal.py   ← deterministic product + bank ranking (NEVER LLM-invented)
```

**Key design principle from research:** Facts → RAG + rules engine. Behavior → LLM dialogue. Banks and products are **never** LLM-generated.

### New files

| File | Purpose |
|------|---------|
| `chat_state.py` | Deal slots, missing-slot logic, question templates, ready-for-match |
| `llm_client.py` | Unified client: Ollama (open-weight) → OpenAI → rules |
| `knowledge_rag.py` | Keyword RAG over YAML content (no embedding deps yet) |
| `guardrails.py` | Rate/approval boundaries, prompt injection, output sanitization |
| `chat_engine.py` | Multi-turn orchestrator: discover → confirm → package |
| `static/chat.html` | Chat UI with deal profile sidebar |
| `static/chat-client.js` | Frontend client |
| `test_chat_engine.py` | 8 automated scenario tests |

### Modified files

| File | Change |
|------|--------|
| `api/main.py` | Added `/api/chat`, `/api/chat/opening`, `/health`, serves chat UI at `/` |
| `match_deal.py` | Fixed owner-occupied detection + `$3.1 million` price parsing |
| `build_borrower_site.py` | Copies `chat.html` + `chat-client.js` to site |
| `.env.example` | Added `LENNI_LLM_PROVIDER`, `LENNI_OLLAMA_MODEL`, `OLLAMA_HOST` |

---

## Model selection (mapped from research doc)

| Component | Implementation | Research recommendation |
|-----------|----------------|-------------------------|
| Discovery dialogue | `llm_client.generate_reply()` via Ollama | DeepSeek V4-Flash / Qwen 3.6-27B |
| Slot extraction | JSON mode Ollama/OpenAI; rules fallback | Constrained decoding |
| Product + bank match | `match_deal()` rules + FFIEC | GraphRAG (future); rules today |
| Knowledge retrieval | `knowledge_rag.py` keyword RAG | LlamaIndex + hybrid retrieval |
| Guardrails | 3-layer: input check, output sanitize, architectural (match_deal) | Required for financial domain |
| Math | Not in scope yet — no LLM arithmetic | Python tools only |

**Default provider when Ollama unavailable:** `rules` (keyword parser from `match_deal.py`)  
**Privacy-first path:** Set `LENNI_LLM_PROVIDER=ollama` + run Qwen2.5/3.6 locally

---

## Conversation flow

```
Phase: discover
  → Extract slots from each message
  → Ask next missing slot (intent → type → city → price → units/acres)
  → RAG retrieves relevant product/scenario chunks

Phase: confirm
  → Summarize deal profile
  → Borrower replies "yes"

Phase: package
  → match_deal(use_llm=False) — deterministic
  → Return: product, banks, prep list, first-call script, next steps
  → Follow-up questions (email draft, why this bank) supported
```

---

## How to run

### 1. Start API (includes chat UI at http://127.0.0.1:8000)

```bash
cd ONLY_TEXAS_SINCE_2025
source ../.venv/bin/activate
python run_match_api.py
# → http://127.0.0.1:8000  (chat UI)
# → http://127.0.0.1:8000/health
```

### 2. Open-weight LLM via Ollama (optional)

```bash
# Install Ollama, then:
ollama pull qwen2.5:14b

export LENNI_LLM_PROVIDER=ollama
export LENNI_OLLAMA_MODEL=qwen2.5:14b
python run_match_api.py
```

Per research doc, recommended models when available:
- **Dev/local:** `qwen2.5:14b` or `qwen3.6:27b` (Apache 2.0)
- **Production GPU:** DeepSeek V4-Flash or GLM-5.2 via vLLM
- **Avoid for recommendations:** Kimi K2.6 (explicitly weak on high-stakes single-turn financial reasoning)

### 3. OpenAI fallback

```bash
export LENNI_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
python run_match_api.py
```

### 4. Rules-only (no LLM, fully offline)

```bash
export LENNI_LLM_PROVIDER=rules
python run_match_api.py
```

---

## Test results

### Automated tests — 3 consecutive runs, all passed

```
test_chat_engine.py:  8/8 passed (×3 runs)
test_match_deal.py:   3/3 passed
```

| Test | Result |
|------|--------|
| `test_opening_message` | PASS |
| `test_slot_extraction_land` | PASS |
| `test_multifamily_full_flow` | PASS — bridge loan + 3+ banks |
| `test_ci_working_capital` | PASS — parent_key=ci |
| `test_land_hold_brenham` | PASS — parent_key=con, intent=hold |
| `test_guardrail_rate_request` | PASS — blocks rate quotes |
| `test_rag_retrieval` | PASS — returns MF/bridge chunks |
| `test_owner_occupied_waco` | PASS — parent_key=own (after parser fix) |

### Manual conversation scenarios

#### Scenario 1: Multifamily value-add bridge (Fort Worth, $4.2M)

| Turn | User | System phase | Key slots |
|------|------|--------------|-----------|
| 1 | 40-unit apartment value-add bridge in Fort Worth, $4.2 million | confirm | mf, value_add, 40 units, $4.2M |
| 2 | yes | package | — |

**Output:**
- Product: **Apartment bridge loan**
- Banks: Titan Bank (19% MF), NexBank (11%), North Dallas Bank (9%)

#### Scenario 2: Land hold (Brenham, 12.4 acres, $849k)

| Turn | User | System phase | Key slots |
|------|------|--------------|-----------|
| 1 | 12.4 acre land near Brenham TX $849k holding for investment | confirm | con, hold, 12.4 ac, $849k |
| 2 | yes | package | — |

**Output:**
- Product: **Land development & lot loans**
- Banks: Bank of South Texas, Cowboy Bank, Peoples State Bank

#### Scenario 3: C&I working capital (Houston, $2M)

| Turn | User | System phase | Key slots |
|------|------|--------------|-----------|
| 1 | working capital line for manufacturing in Houston $2M | confirm | ci, Houston, $2M |
| 2 | yes | package | — |

**Output:**
- Product: **Working capital line of credit**
- Banks: Unity National Bank of Houston, Gulf Capital Bank, Agility Bank

### API integration test

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok","service":"lenni-borrower-api","llm_provider":"rules"}

curl -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"40-unit value-add bridge Fort Worth $4.2M","reset":true}'
# → phase: confirm, slots populated, session_id returned
```

---

## Bug fixes during build

1. **Owner-occupied misclassified as land** — `"my manufacturing business operates out of"` did not match `operate` word boundary. Fixed patterns in `match_deal.py` + boosted `own` score.
2. **`$3.1 million` parsed as $3.10** — Added `million` to price regex patterns.
3. **Ollama not installed on dev machine** — Auto-fallback to `rules` provider; documented Ollama setup for open-weight path.

---

## What's NOT built yet (research doc phase 2+)

| Item | Research recommendation | Status |
|------|-------------------------|--------|
| GraphRAG (Neo4j) | Product ↔ eligibility ↔ lender graph | Not started — flat RAG only |
| Embedding-based retrieval | Qwen3-Embedding-8B + pgvector | Not started — keyword RAG |
| Constrained decoding (XGrammar) | vLLM + Pydantic schemas | JSON mode via Ollama only |
| Python calc tools (DTI, DSCR, LTV) | Never LLM math | Not started |
| QLoRA fine-tune on interview YAML | Behavior adaptation | Awaiting interview sheet answers |
| Session persistence (Redis/DB) | Production | In-memory dict only |
| Llama Guard input classifier | 89–94% catch rate | Regex guardrails only |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LENNI_LLM_PROVIDER` | auto | `ollama`, `openai`, or `rules` |
| `LENNI_OLLAMA_MODEL` | `qwen2.5:14b` | Ollama model tag |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama API base |
| `OPENAI_API_KEY` | — | OpenAI fallback |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `LENNI_CORS_ORIGINS` | localhost | CORS for chat UI |

---

## API reference

### `GET /health`
Returns service status and active LLM provider.

### `GET /api/chat/opening`
Returns Lenni intro message.

### `POST /api/chat`
```json
{
  "message": "40-unit bridge in Fort Worth $4.2M",
  "session_id": "optional-uuid-from-prior-turn",
  "reset": false
}
```

Response:
```json
{
  "session_id": "uuid",
  "reply": "assistant markdown",
  "state": { "phase", "slots", "missing_slots", "ready_for_match" },
  "provider": "rules|ollama|openai",
  "package_ready": true,
  "match_result": { ... }
}
```

---

## Compliance notes (from research doc)

- All bank recommendations cite **FFIEC Call Report portfolio mix** — not credit policy
- Rate/approval requests are **refused** with redirect to preparation guidance
- Disclaimer appended to all loan packages
- Human-in-the-loop recommended before borrowers act on bank shortlist

---

## Next steps

1. Run boss/colleague interview using `content/borrower_llm_interview_sheet.md` → feed answers into RAG
2. Install Ollama + multi-model routing and re-run `eval_routing_comparison.py`
3. Deploy API to AWS; point `LENNI_API_BASE` from static site
4. Add embedding RAG (pgvector) when interview Q&A corpus grows
5. Add DSCR/LTV Python tools before accepting financial doc uploads

---

## Task-based model routing (July 5, 2026 — eval pass)

### What was added

| File | Purpose |
|------|---------|
| `slot_merger.py` | Merge turn + context extractions; detect disagreements |
| `llm_client.py` | Task routing: separate chat/extract/extract_alt models |
| `eval/task_routing_eval_cases.yaml` | 28 golden eval cases (12 multi-turn) |
| `eval_routing_comparison.py` | Baseline vs routing comparison runner |
| `eval/routing_comparison_report.md` | Full per-case report |
| `eval/routing_comparison_results.json` | Machine-readable results |

### Enable / disable

```bash
# Task routing ON (default)
export LENNI_TASK_ROUTING=true

# Baseline single-pass
export LENNI_TASK_ROUTING=false

# Ollama multi-model routing
export LENNI_LLM_PROVIDER=ollama
export LENNI_OLLAMA_MODEL_CHAT=llama3.3:70b
export LENNI_OLLAMA_MODEL_EXTRACT=qwen2.5:14b
export LENNI_OLLAMA_MODEL_EXTRACT_ALT=deepseek-r1:14b
```

### Eval results (rules provider, 28 cases)

| Metric | Baseline | Task routing | Delta |
|--------|----------|--------------|-------|
| Critical field accuracy | 75.5% | 75.5% | +0.0pp |
| All field accuracy | 88.5% | **89.4%** | **+0.9pp** |
| Perfect cases | 16/28 | **17/28** | **+1** |
| Routing wins | — | 1 (E16) | Baseline wins: 0 |

**Key win (E16):** Multi-turn correction — borrower says land in Brenham, then corrects to 40-unit MF Fort Worth. Routing resolves to correct `parent_key=mf`, `price_n=$4.2M`; baseline kept stale `$849k` from turn 1.

**Shared failures (both modes):** Parser gaps on owner-occupied intent (E04, E15, E20), farmland vs acres (E08), duplex→res (E09), equipment-only C&I (E25). These need parser/LLM improvements, not routing alone.

### Re-run eval

```bash
cd ONLY_TEXAS_SINCE_2025
LENNI_LLM_PROVIDER=rules python eval_routing_comparison.py
```

---

*Document: AI_interface_feature_history.md · Updated: July 5, 2026*
