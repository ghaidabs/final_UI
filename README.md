# InVoice Agent

A **bilingual (French / English) voice assistant** for invoicing SaaS platform.  
Users speak natural-language commands — *"Crée une facture pour Ahmed, 3 claviers à 45 dinars"* — and the agent extracts intents, resolves entities, and drives the invoicing API through a structured pipeline.

> **Status — MVP / active development.**  
> Core pipeline (STT → NLU → Dispatcher → Response) is functional.  
> TTS, LiveKit integration, FastAPI server, and production SaaS client are scaffolded but not yet implemented.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Structure](#project-structure)
3. [Pipeline Layers](#pipeline-layers)
   - [Speech-to-Text (STT)](#1-speech-to-text-stt)
   - [Validation & PII Redaction](#2-validation--pii-redaction)
   - [Natural Language Understanding (NLU)](#3-natural-language-understanding-nlu)
   - [Normalizer & Fuzzy Matching](#4-normalizer--fuzzy-matching)
   - [Retrieval-Augmented Generation (RAG)](#5-retrieval-augmented-generation-rag)
   - [Dispatcher](#6-dispatcher)
   - [Templates (Response Generation)](#7-templates-response-generation)
   - [Text-to-Speech (TTS)](#8-text-to-speech-tts)
4. [Schemas](#schemas)
5. [Session Management](#session-management)
6. [API Layer & Mock System](#api-layer--mock-system)
7. [Server](#server)
8. [Getting Started](#getting-started)
9. [Environment Variables](#environment-variables)

---

## Architecture Overview

```
┌──────────┐    PCM audio     ┌──────────┐   transcript    ┌──────────────┐
│  User /  │ ───────────────► │   STT    │ ──────────────► │  Validator   │
│  Mic     │                  │(Deepgram)│                 │ (PII redact) │
└──────────┘                  └──────────┘                 └──────┬───────┘
                                                                  │
                                                          safe transcript
                                                                  │
                                                                  ▼
┌──────────────┐   VoiceResponse   ┌────────────┐   Intent    ┌───────┐
│  Templates   │ ◄──────────────── │ Dispatcher │ ◄────────── │  NLU  │
│ (fr/en text) │                   │            │             │(Groq) │
└──────┬───────┘                   └─────┬──────┘             └───┬───┘
       │                                 │                        │
       ▼                                 ▼                        │
┌──────────┐                    ┌──────────────┐          ┌───────┴───────┐
│   TTS    │                    │  SaaS Client │          │  Normalizer   │
│  (TODO)  │                    │  (mock / real)│         │  Fuzzy / RAG  │
└──────────┘                    └──────────────┘          └───────────────┘
```

---

## Project Structure

```
voice assistant agent/
├── agent/                 
│   ├── main.py             # CLI REPL — text input or voice mode
│   ├── stt.py              # Deepgram streaming STT session
│   ├── stt_console.py      # Standalone mic → STT debugger
│   ├── nlu.py              # LLM-powered intent extraction + price-only extractor
│   ├── dispatcher.py       # Intent routing, disambiguation, confirmation flows
│   ├── validator.py        # PII redaction (pure regex)
│   ├── normalizer.py       # Invoice-number normalization
│   ├── fuzzy.py            # Fuzzy entity matching (rapidfuzz)
│   ├── session.py          # Session state & user context dataclasses
│   ├── tts.py              # Text-to-Speech
│   └── prompts/
│       └── intent_extraction.txt   # System prompt for NLU
│
├── api/                    
│   ├── mock_saas_client.py # Mock client backed by local JSON DB
│   └── saas_client.py      # Real HTTP client
│
├── rag/                    
│   ├── embeddings.py       # Sentence-transformer embeddings
│   ├── indexer.py          # Qdrant vector indexing
│   └── retriever.py        # Similarity search against Qdrant
│
├── schemas/                # Pydantic data models
│   ├── intents.py         
│   └── responses.py        
│
├── templates/              # Spoken-text response builders (fr/en)
│   ├── clarification.py    
│   ├── invoice.py          
│   ├── client_lookup.py    
│   └── payment_status.py   
│
├── mock/                   
│   ├── db.py               
│   ├── clients.json        
│   ├── invoices.json       
│   ├── products.json       
│   ├── companies.json      
│   └── users.json          
│
├── server/                
│   ├── main.py            
│   ├── auth.py            
│   └── routes/
│       ├── audio_proxy.py      
│       └── livekit_token.py    
│
├── frontend/              
│
├── .env.example            
├── .gitignore
└── requirements.txt
```

---

## Pipeline Layers

### 1. Speech-to-Text (STT)

| File | Description |
|------|-------------|
| `agent/stt.py` | Production `STTSession` class wrapping **Deepgram Nova-3** streaming WebSocket |
| `agent/stt_console.py` | Standalone dev tool — streams from system microphone, prints per-word confidence with color coding |

**Key details:**

- **Model:** `nova-3` with `language: "multi"` (auto-detects French/English).
- **Features enabled:** smart formatting, punctuation, numeral conversion, VAD events, interim results.
- Outputs a `TranscriptResult` dataclass containing the full transcript, per-word confidence scores, and detected language.
- **Confidence thresholds:** words below `0.55` are flagged; overall transcript below `0.6` is marked low-confidence.
- Low-confidence words are annotated with a `⚠` marker (via `annotate_low_confidence()`) before being sent to the NLU, so the LLM knows which tokens are uncertain.
- **PII redaction in STT:** `stt.py` outputs the **raw transcript** (no PII redaction at the STT level). Redaction happens downstream in `nlu.py` before sending to the LLM.
- `LiveKitAudioSource` adapter is stubbed — will bridge LiveKit's `AudioStream` to `STTSession` once integrated.

**Voice mode in the REPL:**

The `main.py` REPL supports a `voice` command that captures one full spoken utterance via the microphone, transcribes it through `STTSession`, annotates low-confidence words, and feeds the result directly into the NLU → Dispatcher pipeline.

---

### 2. Validation & PII Redaction (WIP)

| File | Description |
|------|-------------|
| `agent/validator.py` | Redacts sensitive data from transcripts before they reach the LLM |

The validator uses a lightweight, self-contained pipeline:

1. **Normalize spoken symbols:** converts spoken `"dot"` / `"point"` → `.` and `"at"` / `"arobase"` → `@`, collapses digit runs separated by spaces/dashes.
2. **Shield invoice numbers:** before redacting, any digit runs near invoice context words (`facture`, `invoice`, `numéro`, or the company slug) are temporarily shielded with placeholder tokens so they aren't caught by the generic phone-number regex.
3. **Redact patterns:**
   - Email addresses → `<EMAIL>`
   - Tunisian *matricule fiscale* (tax ID, format `1234567X/X/X/000`) → `<TAX_ID>`
   - IBAN codes → `<IBAN>`
   - Long digit runs (7–19 digits) → `<PHONE>`
4. **Unshield:** restore the invoice-number digits.

The `redact_pii()` function accepts an optional `company_slug` parameter to improve shielding accuracy.

> **Change from previous version:** GuardrailsAI (only English support), Presidio/spaCy (not robust for STT transcripts) have been replaced by this regex-only approach.

---

### 3. Natural Language Understanding (NLU)

| File | Description |
|------|-------------|
| `agent/nlu.py` | Sends redacted transcript to an LLM and parses structured intent JSON |
| `agent/prompts/intent_extraction.txt` | System prompt defining all intent schemas and extraction rules |

**How it works:**

1. The transcript is PII-redacted via `redact_pii(transcript, company_slug)`.
2. The safe transcript is sent to **Groq** (model: `openai/gpt-oss-120b`) with `temperature=0.1` and `response_format: json_object`.
3. The LLM returns a JSON object matching one of the defined intent schemas.
4. The raw JSON is validated into the corresponding **Pydantic** intent model.
5. **Invoice number normalization** is applied for `check_invoice`, `check_payment`, and `add_line_item` intents:
   - If normalization succeeds, confidence is boosted to at least `0.9`.
   - If it fails (not enough digits), the field is nulled, confidence capped at `0.4`, and `invoice_number` added to `low_confidence_fields`.
6. `extract_intent_with_context()` handles **multi-turn follow-ups** — if the session is awaiting a specific field, the pending transcript is prepended for context. It also accepts a `language` parameter to pass the STT-detected language to the LLM.

**`extract_price_only(transcript)` — dedicated price extractor:**

When the dispatcher is awaiting a unit price from the user, this function extracts a numeric value without running full intent extraction:
1. First tries a regex match for decimal numbers in the transcript.
2. Falls back to a lightweight LLM call (`temperature=0.0`) that returns `{"price": number_or_null}`.

**Supported intents:**

| Intent | Entities extracted |
|--------|-------------------|
| `create_invoice` | `client_name`, `articles[]` (product, qty, price, unit), `currency`, `due_date`, TVA/stamp flags, payment method |
| `lookup_client` | `client_name` |
| `check_invoice` | `invoice_number` or `client_name` |
| `add_line_item` | `invoice_number`, `product_name`, `quantity`, `unit_price`, `unit` |
| `check_payment` | `invoice_number` or `client_name` |
| `confirm` | (confirms a pending action) |
| `cancel` | ( cancels a pending action) |
| `unknown` | `raw_text` |

---

### 4. Normalizer & Fuzzy Matching

| File | Description |
|------|-------------|
| `agent/normalizer.py` | Converts spoken/partial invoice numbers into the canonical format `SLUG_FYYYYMM-SEQ` |
| `agent/fuzzy.py` | RapidFuzz-based entity resolution for client names and product names |

- **Normalizer:** extracts the company slug and 9+ digits, reassembles into `SLUG_FYYYYMM-SEQ`. Returns `None` if fewer than 9 digits are found (triggers a clarification flow).
- **Fuzzy matching:** uses `WRatio` scorer with a floor of 75%. Returns top-K matches with their `_fuzzy_score` attached, so the dispatcher can decide whether to auto-resolve or ask for confirmation.

---

### 5. Retrieval-Augmented Generation (RAG)

| File | Description |
|------|-------------|
| `rag/embeddings.py` | Produces dense vectors using `sentence-transformers/all-MiniLM-L6-v2` |
| `rag/indexer.py` | Creates and upserts into per-company Qdrant collections |
| `rag/retriever.py` | Cosine similarity search with a floor of `0.55` |

**How it's used:**

The RAG layer is a **fallback** for entity resolution. When a user says a client or product name that doesn't match via exact substring or fuzzy matching, the system:

1. Indexes all clients/products for the company into Qdrant (lazy, once).
2. Embeds the spoken query and runs a similarity search.
3. Returns candidates above the similarity floor.

Collections are named `{entity_type}s_{company_id}` (e.g., `clients_1`, `products_2`).

**Entity resolution cascade** (in `MockSaasClient`):

```
Exact substring match → Fuzzy match (rapidfuzz) → Semantic match (RAG)
```

---

### 6. Dispatcher

| File | Description |
|------|-------------|
| `agent/dispatcher.py` | Routes intents to handlers, orchestrates business logic, disambiguation, and confirmation flows |

**Key behaviors :**

#### Confidence gating with recoverable fields

- Intents below `0.7` confidence normally trigger a clarification prompt.
- **Exception:** if every low-confidence field is in the `RECOVERABLE` set (`invoice_number`, `unit_price`), the dispatcher lets the handler proceed — these fields have their own clarification flows inside the handler that will ask the user directly.

#### Disambiguation system (`pending_disambiguation`)

When entity resolution (client or product) returns a single fuzzy/semantic match, the dispatcher doesn't auto-accept it. Instead:

1. The ambiguous candidate is stashed in `session.pending_disambiguation` along with the `kind` (`"client"` or `"product"`), the original intent, and any already-resolved line items.
2. The user is asked to confirm: *"Did you mean X? Please confirm."*
3. On **confirm** → `_resolve_disambiguation()` accepts the candidate and resumes the original flow (create invoice, add line item, or lookup client).
4. On **cancel** → the user is asked to clarify: *"Okay, who/what did you mean instead?"* and the session enters an `awaiting_field` state.
5. For `create_invoice` with multiple articles, disambiguation can pause and resume mid-list — already-resolved line items are preserved in `resolved_line_items`.

#### `create_invoice` flow

1. Resolve client (exact → fuzzy → RAG; ambiguous = disambiguation prompt).
2. Check for missing unit prices → stash `awaiting_article_indices` and ask user.
3. Resolve each product name via `_build_line_items_or_pause()` — may pause for disambiguation at any article.
4. Build a draft via `_finalize_invoice_draft()` and store it in `session.pending_draft`.
5. Return the draft summary with `requires_confirmation=True`.
6. User says "confirm" → draft is finalized and saved.
7. User says "cancel" → draft is discarded.

#### `add_line_item` flow

1. If `invoice_number` is missing → ask for it (new `awaiting_field="invoice_number"` state).
2. If `unit_price` is missing → ask for it.
3. Resolve product name → may trigger disambiguation.
4. Verify the target invoice exists.
5. **Confirmation required:** the line item is stashed in `session.pending_line_item` and the user is prompted to confirm before the mutation happens.
6. On confirm → `add_line_item` is called on the SaaS client.
7. On cancel → *"Okay, I discarded that line item."*

#### `resume_awaiting_field()`

A top-level function called by `main.py` **before** NLU extraction when the session is awaiting a specific field. Handles two cases:
- **`invoice_number`:** normalizes the user's answer directly and re-dispatches the stashed intent.
- **`unit_price`:** uses `extract_price_only()` (regex + LLM fallback) to extract the number, patches the stashed intent, and re-dispatches.

#### `_handle_confirm` / `_handle_cancel`

These now handle three independent pending states in priority order:

| Priority | Pending state | Confirm action | Cancel action |
|----------|--------------|----------------|---------------|
| 1 | `pending_disambiguation` | Accept fuzzy candidate, resume flow | Ask *"who/what did you mean?"* |
| 2 | `pending_line_item` | Execute `add_line_item` mutation | Discard line item |
| 3 | `pending_draft` | Finalize invoice | Discard draft |

---

### 7. Templates (Response Generation)

| File | Description |
|------|-------------|
| `templates/clarification.py` | Bilingual string table with `t(key, language, **kwargs)` interpolation |
| `templates/invoice.py` | Spoken responses for drafts, invoice details, invoice lists, added line items |
| `templates/client_lookup.py` | Spoken responses for client lookups |
| `templates/payment_status.py` | Spoken responses for payment status queries |

All templates produce **natural language text** in either French or English, determined by the detected language of the user's utterance.

---

### 8. Text-to-Speech (TTS)

| File | Description |
|------|-------------|
| `agent/tts.py` | **Placeholder** — not yet implemented |

Will convert the `VoiceResponse.spoken_text` back to audio for the user. Planned integration via LiveKit plugins.

---

## Schemas

All data models live in `schemas/` and use **Pydantic v2**.

- **`intents.py`** — `IntentType` enum + one Pydantic model per intent type, all inheriting from `BaseIntent` (which carries `confidence`, `low_confidence_fields`, `raw_transcript`, and `language`).
- **`responses.py`** — `VoiceResponse` with built-in consistency validators (e.g., can't have `success=True` with an error, can't have `draft_payload` without `requires_confirmation`).

---

## Session Management

Defined in `agent/session.py`:

- **`UserContext`** — immutable per-session: `user_id`, `company_id`, `role`, `company_slug`.
- **`SessionState`** — mutable conversation state:

| Field | Type | Purpose |
|-------|------|---------|
| `pending_draft` | `dict?` | Holds an invoice draft until confirmed/cancelled |
| `pending_line_item` | `dict?` | Holds a line-item addition until confirmed/cancelled |
| `pending_transcript` | `str?` | Original transcript to prepend when resuming |
| `pending_disambiguation` | `dict?` | Stashed fuzzy candidate + original intent for disambiguation |
| `pending_confirmation` | `bool` | Flags that a confirm/cancel is expected |
| `awaiting_field` | `str?` | Which field the user needs to supply (`unit_price`, `invoice_number`, `client_name`, `product_name`) |
| `awaiting_intent` | `Any?` | The full intent object being built incrementally |
| `awaiting_article_indices` | `list[int]?` | Which articles in a `create_invoice` are missing prices |
| `last_intent` | `str?` | Tracks the last intent type for context |

---

## API Layer & Mock System

| File | Description |
|------|-------------|
| `api/mock_saas_client.py` | `MockSaasClient` — async façade over the local JSON DB, with entity resolution cascade |
| `api/saas_client.py` | **Placeholder** for the real HTTP client (`httpx`) that will hit the production SaaS API |
| `mock/db.py` | In-memory database backed by JSON seed files, with CRUD operations, pagination, and invoice number sequencing |

**Multi-tenancy:** All queries are scoped by `company_id`. The mock DB enforces tenant isolation — a user from ACME cannot see NOVA's clients or invoices.

**Duplicate line-item merging:** When `add_line_item` is called with a designation that already exists on the invoice, the existing article's quantity is incremented and its unit price is updated (instead of appending a duplicate).

**Mock data files:**

| File | Content |
|------|---------|
| `companies.json` | 2 companies (ACME, NOVA) |
| `users.json` | 3 users across roles (ADMIN, OWNER) |
| `clients.json` | Sample client records per company |
| `products.json` | Sample product catalog per company |
| `invoices.json` | Sample invoices in various statuses |

---

## Server

The `server/` directory is scaffolded for a **FastAPI** application that will expose:

- **WebSocket audio proxy** — stream browser audio to the STT pipeline.
- **LiveKit token endpoint** — issue LiveKit room tokens for real-time voice sessions.
- **JWT auth middleware** — validate tokens from the SaaS platform.

---

## Getting Started

### Prerequisites

- Python 3.11+
- A Deepgram API key (for STT)
- A Groq API key (for NLU)
- (Optional) A Hugging Face token (`HF_TOKEN`) for gated sentence-transformer models
- (Optional) Qdrant instance (for RAG)
- (Optional) `sounddevice` + `numpy` for voice mode / microphone testing

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPGRAM_API_KEY` | Deepgram API key for Nova-3 streaming |
| `GROQ_API_KEY` | Groq API key for LLM intent extraction |
| `HF_TOKEN` | Hugging Face token for gated embedding models |
| `QDRANT_ENDPOINT` | Qdrant server URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `LIVEKIT_URL` | LiveKit server URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `SAAS_API_BASE_URL` | Production SaaS API base URL |
| `SAAS_API_TEST_TOKEN` | Test token for the SaaS API |
| `ENV` | Environment flag (e.g., `dev`, `prod`) |

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd "voice assistant agent"

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

### Running

```bash
python -m agent.main
```