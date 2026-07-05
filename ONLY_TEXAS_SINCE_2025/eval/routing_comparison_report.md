# Task-Based Model Routing — Evaluation Report

**Generated:** 2026-07-05 20:43 UTC  
**LLM provider:** `rules` (rules = deterministic parser; Ollama models when configured)  
**Cases:** 28 golden examples from `eval/task_routing_eval_cases.yaml`

---

## Executive summary

| Metric | Baseline (single-pass) | Task routing (dual extract + merge) | Delta |
|--------|------------------------|-------------------------------------|-------|
| Critical field accuracy (parent_key, intent) | 75.5% | 75.5% | +0.0pp |
| All scored field accuracy | 88.5% | 89.4% | +0.9pp |
| Product match (match_deal) | 82.1% | 82.1% | +0.0pp |
| Perfect cases (all fields) | 16/28 | 17/28 | +1 |
| Avg latency per case | 0.12 ms | 0.12 ms | +0.00 ms |

**Routing won on 1 cases** · Baseline won on 0 · Tied on 27

---

## What each mode does

### Baseline (`LENNI_TASK_ROUTING=false`)
- Single extraction pass on **full conversation + current message**
- One model (or rules parser) for both slot extraction and chat
- No disagreement detection

### Task routing (`LENNI_TASK_ROUTING=true`)
- **Turn extractor:** current message only (corrections win)
- **Context extractor:** full conversation log (fills gaps)
- **Merge policy:** turn wins on conflict; flags critical disagreements
- **Separate chat model** (`LENNI_OLLAMA_MODEL_CHAT`) when using Ollama
- **Separate extract models** (`EXTRACT` + `EXTRACT_ALT`) when using Ollama

---

## Cases where routing won

- **E16** — MULTI-TURN correction land to MF
  - Baseline fields: 4 → Routing fields: 5

## Cases where baseline won

_None in this run._

---

## Per-case detail

### E01: MF value-add bridge Fort Worth

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Apartment bridge loan | Apartment bridge loan |

_Identical slot outcomes._

### E02: Land hold Brenham

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Land development & lot loans | Land development & lot loans |

_Identical slot outcomes._

### E03: C&I working capital Houston

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Working capital line of credit | Working capital line of credit |

_Identical slot outcomes._

### E04: Owner-occupied Waco manufacturer

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Owner-occupied property purchase | Owner-occupied property purchase |

_Identical slot outcomes._

### E05: Industrial investor refinance Houston

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 4 | 4 |
| Product | Investor industrial / warehouse loan | Investor industrial / warehouse loan |

_Identical slot outcomes._

### E06: Multifamily acquisition Austin stabilized

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Apartment acquisition loan | Apartment acquisition loan |

_Identical slot outcomes._

### E07: Ground-up construction Dallas

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Investor retail / strip center loan | Investor retail / strip center loan |

_Identical slot outcomes._

### E08: Farmland ranch purchase

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 0 | 0 |
| All fields | 2 | 2 |
| Product | Land development & lot loans | Land development & lot loans |

_Identical slot outcomes._

### E09: Duplex residential (1-4)

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 0 | 0 |
| All fields | 2 | 2 |
| Product | Apartment acquisition loan | Apartment acquisition loan |

_Identical slot outcomes._

### E10: SBA business loan Dallas

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Equipment financing | Equipment financing |

_Identical slot outcomes._

### E11: Multifamily refinance San Antonio

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 4 | 4 |
| Product | Apartment acquisition loan | Apartment acquisition loan |

_Identical slot outcomes._

### E12: Land development College Station

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 3 | 3 |
| Product |  |  |

_Identical slot outcomes._

### E13: Office NNN investor El Paso

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Investor office building loan | Investor office building loan |

_Identical slot outcomes._

### E14: Bridge transitional MF Dallas

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Apartment bridge loan | Apartment bridge loan |

_Identical slot outcomes._

### E15: Owner occupied purchase Tyler

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 0 | 0 |
| All fields | 2 | 2 |
| Product | Investor industrial / warehouse loan | Investor industrial / warehouse loan |

_Identical slot outcomes._

### E16: MULTI-TURN correction land to MF

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 4 | 5 |
| Product | Apartment bridge loan | Apartment bridge loan |
| Disagreements flagged | — | 1 |
| Clarifications | — | 0 |

**Field differences:**
- `price_n`: baseline=849000.0 (✗) · routing=4200000.0 (✓) · expected=4200000

### E17: MULTI-TURN add location then price

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Multifamily value-add / rehab | Multifamily value-add / rehab |
| Disagreements flagged | — | 0 |
| Clarifications | — | 0 |

_Identical slot outcomes._

### E18: MULTI-TURN CI then clarify amount

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Working capital line of credit | Working capital line of credit |
| Disagreements flagged | — | 1 |
| Clarifications | — | 0 |

_Identical slot outcomes._

### E19: MULTI-TURN intent change acquire to refinance

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 3 | 3 |
| Product | Investor industrial / warehouse loan | Investor industrial / warehouse loan |
| Disagreements flagged | — | 2 |
| Clarifications | — | 0 |

_Identical slot outcomes._

### E20: MULTI-TURN owner-occupy clarification

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Owner-occupied property purchase | Owner-occupied property purchase |
| Disagreements flagged | — | 1 |
| Clarifications | — | 0 |

_Identical slot outcomes._

### E21: Raw land lot loan Midland

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Land development & lot loans | Land development & lot loans |

_Identical slot outcomes._

### E22: Multifamily perm takeout

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Multifamily permanent takeout | Multifamily permanent takeout |

_Identical slot outcomes._

### E23: Retail strip investor CRE

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 4 | 4 |
| Product | Investor retail / strip center loan | Investor retail / strip center loan |

_Identical slot outcomes._

### E24: MULTI-TURN conflicting signals (should clarify or resolve to latest)

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 5 | 5 |
| Product | Apartment bridge loan | Apartment bridge loan |
| Disagreements flagged | — | 0 |
| Clarifications | — | 0 |

_Identical slot outcomes._

### E25: Equipment term loan C&I

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 0 | 0 |
| All fields | 2 | 2 |
| Product | Ground-up commercial construction | Ground-up commercial construction |

_Identical slot outcomes._

### E26: MULTI-TURN three turns gradual reveal

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 2 | 2 |
| All fields | 4 | 4 |
| Product | NNN / single-tenant net lease loan | NNN / single-tenant net lease loan |
| Disagreements flagged | — | 2 |
| Clarifications | — | 0 |

_Identical slot outcomes._

### E27: Agricultural production loan

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 3 | 3 |
| Product | Farmland purchase loan | Farmland purchase loan |

_Identical slot outcomes._

### E28: MULTI-TURN bridge then units

| | Baseline | Task routing |
|--|----------|--------------|
| Critical fields | 1 | 1 |
| All fields | 4 | 4 |
| Product | Apartment bridge loan | Apartment bridge loan |
| Disagreements flagged | — | 3 |
| Clarifications | — | 1 |

**Field differences:**
- `intent`: baseline=value_add (✗) · routing=acquire (✗) · expected=bridge

---

## Critical failures (baseline)

E04, E07, E08, E09, E11, E13, E15, E20, E22, E25, E28

## Critical failures (routing)

E04, E07, E08, E09, E11, E13, E15, E20, E22, E25, E28

---

## Re-run instructions

```bash
cd ONLY_TEXAS_SINCE_2025
LENNI_LLM_PROVIDER=rules python eval_routing_comparison.py

# With Ollama task routing:
LENNI_LLM_PROVIDER=ollama \
LENNI_OLLAMA_MODEL_CHAT=llama3.3:70b \
LENNI_OLLAMA_MODEL_EXTRACT=qwen2.5:14b \
LENNI_OLLAMA_MODEL_EXTRACT_ALT=deepseek-r1:14b \
python eval_routing_comparison.py
```
