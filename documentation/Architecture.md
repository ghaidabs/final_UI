# Architecture Overview

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
│(ElevenLb)│                    │ (mock / real)│          │Fuzzy/Semantic │
└──────────┘                    └──────────────┘          └───────────────┘
```

---

## Project Structure

```
InVoice-agent-main/
├── agent/                          
│   ├── main.py                     # CLI REPL — text or voice mode
│   ├── livekit_agent.py            # LiveKit agent worker (real-time voice)
│   ├── core/                       
│   │   ├── dispatcher.py           # Intent routing, disambiguation, confirmation flows
│   │   ├── pipeline.py             # Dispatch entry point
│   │   ├── session.py              # SessionState & UserContext dataclasses
│   │   ├── user_context.py         # new session helper
│   │   └── warmup.py               # Background search warm-up thread
│   ├── nlp/                        
│   │   ├── nlu.py                  # LLM-powered intent extraction
│   │   ├── validator.py            # PII redaction (regex-based)
│   │   ├── normalizer.py           # Invoice-number normalization
│   │   └── normalizer.py           # Invoice-number normalization
│   ├── speech/                     
│   │   ├── stt.py                  # Deepgram Nova-3 streaming STT session
│   │   ├── stt_console.py          # Standalone mic → STT debugger
│   │   ├── tts.py                  # ElevenLabs streaming TTS
│   │   └── lang_detect.py          # Language detection & resolution (fr/en)
│   └── prompts/
│       └── intent_extraction.txt   # System prompt for NLU
│
├── api/                           
│   ├── mock_saas_client.py         # Mock client backed by local JSON DB, with entity cascade
│   └── saas_client.py              # Real HTTP client (placeholder)
│
├── search/                         
│   ├── embeddings.py               # Sentence-transformer embeddings
│   ├── fuzzy.py                    # Fuzzy entity matching (rapidfuzz)
│   ├── indexer.py                  # Qdrant vector indexing
│   └── retriever.py                # Similarity search against Qdrant
│
├── schemas/                        
│   ├── intents.py                  # IntentType enum + per-intent Pydantic models
│   └── responses.py                # VoiceResponse with consistency validators
│
├── templates/                      
│   ├── clarification.py            # Bilingual string table
│   ├── invoice.py                  # Drafts, invoice details, invoice lists, added line items
│   ├── client_lookup.py            # Client lookup responses
│   ├── payment_status.py           # Payment status query responses
│   └── spoken_format.py            # Formatting helpers
│
├── mock/                         
│   ├── db.py                       # In-memory DB backed by JSON seed files, CRUD, pagination
│   └── data/
│       ├── clients.json            # Sample client records per company
│       ├── companies.json          # 2 companies (ACME, NOVA)
│       ├── invoices.json           # Sample invoices in various statuses
│       ├── products.json           # Sample product catalog per company
│       └── users.json              # 3 users across roles (ADMIN, OWNER)
│
├── server/                        
│   ├── main.py                     # App factory, CORS middleware, router mounts
│   ├── auth.py                     # JWT authentication
│   ├── livekit_token.py            # Issues LiveKit room tokens
│   └── dev_token.py                # Prints a signed JWT for mock users
│
├── UI/                             
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx                # App entry point 
│       ├── components/             
│       │   ├── VoiceAgentPanel/    # Main voice agent UI panel
│       │   ├── DisplayData.jsx     # Structured data renderer
│       │   ├── IntentSuggestions.jsx
│       │   ├── InvoiceDraftCard.jsx
│       │   ├── LineItemCard.jsx
│       │   └── TaskCard.jsx
│       ├── hooks/
│       │   └── useVoiceAgent.js    # LiveKit connection & data channel hook
│       └── utils/
│           ├── i18n.js             # Bilingual UI strings
│           ├── intents.js          # Intent metadata & icons
│           └── taskGrouping.js     # Task grouping logic
│
├── documentation/                  
│   ├── Architecture.md             
│   ├── LiveKit.md                  
│   ├── Search.md                   
│   └── UI.md                      
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
| `agent/speech/stt.py` | Production `STTSession` class wrapping **Deepgram Nova-3** streaming WebSocket |
| `agent/speech/stt_console.py` | Standalone dev tool — streams from system microphone, prints per-word confidence with color coding |

**Key details:**

- **Model:** `nova-3` with `language: "multi"` (auto-detects French/English).
- **Features enabled:** smart formatting, punctuation, numeral conversion, VAD events, interim results.
- Outputs a `TranscriptResult` dataclass containing the full transcript, per-word confidence scores, and detected language.
- **Confidence thresholds:** words below `0.55` are flagged; overall transcript below `0.6` is marked low-confidence.
- Low-confidence words are annotated with a `⚠` marker (via `annotate_low_confidence()`) before being sent to the NLU, so the LLM knows which tokens are uncertain.
- **PII redaction in STT:** `stt.py` outputs the **raw transcript** (no PII redaction at the STT level). Redaction happens downstream in `nlu.py` before sending to the LLM.
- `LiveKitAudioSource` adapter bridges LiveKit's `AudioStream` to `STTSession` for the real-time voice path.

**Voice mode in the REPL:**

The `agent/main.py` REPL supports a `voice` command that captures one full spoken utterance via the microphone, transcribes it through `STTSession`, annotates low-confidence words, and feeds the result directly into the NLU → Dispatcher pipeline.

---

### 2. Language Detection

| File | Description |
|------|-------------|
| `agent/speech/lang_detect.py` | Detects and resolves the user's language from STT output or transcript text |

**Key details:**

- **Supported languages:** `fr` (French) and `en` (English). Default is `fr`.
- `detect_language(text)` — uses `langdetect` to identify the language of a text string. Falls back to `fr` on failure.
- `resolve_language(tag, text)` — tries the provided language tag first (from STT), falls back to `detect_language(text)` if the tag is missing or unsupported.
- In the LiveKit agent, language is **locked** to the first detected language for the entire conversation (per participant) to prevent mid-session language switching.

---

### 3. Validation & PII Redaction

| File | Description |
|------|-------------|
| `agent/nlp/validator.py` | Redacts sensitive data from transcripts before they reach the LLM |

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

---

### 4. Natural Language Understanding (NLU)

| File | Description |
|------|-------------|
| `agent/nlp/nlu.py` | Sends redacted transcript to an LLM and parses structured intent JSON |
| `agent/prompts/intent_extraction.txt` | System prompt defining all intent schemas and extraction rules |

**How it works:**

1. The transcript is PII-redacted via `redact_pii(transcript, company_slug)`.
2. The safe transcript is sent to **Groq** with `temperature=0.1` and `response_format: json_object`.
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
| `create_invoice` | `client_name`, `articles[]` (product, qty, price, unit), `currency`, TVA/stamp flags, payment method |
| `lookup_client` | `client_name` |
| `check_invoice` | `invoice_number` or `client_name` |
| `add_line_item` | `invoice_number`, `product_name`, `quantity`, `unit_price`, `unit` |
| `check_payment` | `invoice_number` or `client_name` |
| `confirm` | (confirms a pending action) |
| `cancel` | (cancels a pending action) |
| `unknown` | `raw_text` |

---

### 5. Normalizer

| File | Description |
|------|-------------|
| `agent/nlp/normalizer.py` | Converts spoken/partial invoice numbers into the canonical format `SLUG_FYYYYMM-SEQ` |

- **Normalizer:** extracts the company slug and 9+ digits, reassembles into `SLUG_FYYYYMM-SEQ`. Returns `None` if fewer than 9 digits are found (triggers a clarification flow).

---

### 6. Entity Search (Fuzzy + Semantic)

| File | Description |
|------|-------------|
| `search/fuzzy.py` | RapidFuzz-based fuzzy string matching with a floor of 75% |
| `search/embeddings.py` | Produces dense vectors using `sentence-transformers/all-MiniLM-L6-v2` |
| `search/indexer.py` | Creates and upserts into per-company Qdrant collections |
| `search/retriever.py` | Cosine similarity search with a floor of `0.55` |

**How it's used:**

The search layer is a **fallback** for entity resolution. When a user says a client or product name that doesn't match via exact substring, the system tries fuzzy matching first, then semantic vector search:

1. Indexes all clients/products for the company into Qdrant (lazy, once).
2. Embeds the spoken query and runs a similarity search.
3. Returns candidates above the similarity floor.

Collections are named `{entity_type}s_{company_id}` (e.g., `clients_1`, `products_2`).

**Entity resolution cascade** (in `MockSaasClient`):

```
Exact substring match → Fuzzy match (rapidfuzz) → Semantic match (vector search)
```

> See [Search.md](../documentation/Search.md) for detailed documentation on indexing, retrieval, and the cascade.

---

### 7. Pipeline & Turn Orchestration

| File | Description |
|------|-------------|
| `agent/core/pipeline.py` | `run_turn()` — single entry point that runs one conversation turn |

**`run_turn(transcript, session, saas, language)` flow:**

1. **Check for awaiting field:** if the session is waiting for a specific input (invoice number, unit price, etc.), `resume_awaiting_field()` handles it directly without running full NLU.
2. **NLU extraction:** `extract_intent_with_context()` processes the transcript through PII redaction → LLM → Pydantic validation.
3. **Dispatch:** routes the extracted intent to the appropriate handler.
4. **Attach turn state:** decorates the response with the current session state for the frontend.

---

### 8. Dispatcher

| File | Description |
|------|-------------|
| `agent/core/dispatcher.py` | Routes intents to handlers, orchestrates business logic, disambiguation, and confirmation flows |

**Key behaviors:**

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

1. Resolve client (exact → fuzzy → semantic search; ambiguous = disambiguation prompt).
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

A top-level function called by `pipeline.py` **before** NLU extraction when the session is awaiting a specific field. Handles two cases:
- **`invoice_number`:** normalizes the user's answer directly and re-dispatches the stashed intent.
- **`unit_price`:** uses `extract_price_only()` (regex + LLM fallback) to extract the number, patches the stashed intent, and re-dispatches.

#### Button intents (`build_button_intent`)

The LiveKit agent can receive `confirm` / `cancel` actions from the frontend UI via the data channel. `build_button_intent(action, language)` constructs the corresponding intent object so it can be dispatched through the same pipeline as voice intents.

#### `_handle_confirm` / `_handle_cancel`

These now handle three independent pending states in priority order:

| Priority | Pending state | Confirm action | Cancel action |
|----------|--------------|----------------|---------------|
| 1 | `pending_disambiguation` | Accept fuzzy candidate, resume flow | Ask *"who/what did you mean?"* |
| 2 | `pending_line_item` | Execute `add_line_item` mutation | Discard line item |
| 3 | `pending_draft` | Finalize invoice | Discard draft |

---

### 9. Templates (Response Generation)

| File | Description |
|------|-------------|
| `templates/clarification.py` | Bilingual string table with `t(key, language, **kwargs)` interpolation |
| `templates/invoice.py` | Spoken responses for drafts, invoice details, invoice lists, added line items |
| `templates/client_lookup.py` | Spoken responses for client lookups |
| `templates/payment_status.py` | Spoken responses for payment status queries |
| `templates/spoken_format.py` | Formatting helpers: currency names, amount formatting, digit-by-digit spoken numbers, invoice suffix reading |

All templates produce **natural language text** in either French or English, determined by the detected language of the user's utterance.

**`spoken_format.py` helpers:**

| Function | Purpose |
|----------|---------|
| `spoken_currency(code, language)` | `"TND"` → `"Dinars Tunisiens"` / `"Tunisian Dinars"` |
| `spoken_amount(value, currency, language)` | `45.5, "TND"` → `"45.50 Dinars Tunisiens"` |
| `display_amount(value, currency)` | `45.5, "TND"` → `"45.50 TND"` |
| `spoken_digit_group(group, language)` | `"123"` → `"un deux trois"` |
| `spoken_phone_number(phone, language)` | `"+216 98 000 003"` → `"plus deux un six, neuf huit, ..."` |
| `spoken_invoice_suffix(number, language)` | `"ACME_F202605-001"` → `"deux zéro deux six zéro cinq, zéro zéro un"` |
| `status_phrase(status, language)` | `"paid"` → `"a été payée"` / `"has been paid"` |

---

### 10. Text-to-Speech (TTS)

| File | Description |
|------|-------------|
| `agent/speech/tts.py` | `TTSSession` class wrapping the **ElevenLabs** streaming TTS API |

**Key details:**

- **Provider:** ElevenLabs (`elevenlabs` Python SDK).
- **Language awareness:** accepts an optional `language` parameter from the pipeline. Normalizes it to ISO codes (`"fr"`, `"en"`) and passes it to the ElevenLabs API so the voice model adapts its pronunciation.
- **Streaming synthesis:** uses `text_to_speech.stream()` to receive audio chunks incrementally and buffers them into a single `SynthesisResult`.
- **Playback:** `play_pcm()` in `main.py` decodes the PCM buffer into a NumPy int16 array and plays it via `sounddevice.play(blocking=True)`.

---

## Schemas

All data models live in `schemas/` and use **Pydantic v2**.

- **`intents.py`** — `IntentType` enum + one Pydantic model per intent type, all inheriting from `BaseIntent` (which carries `confidence`, `low_confidence_fields`, `raw_transcript`, and `language`).
- **`responses.py`** — `VoiceResponse` with built-in consistency validators (e.g., can't have `success=True` with an error, can't have `draft_payload` without `requires_confirmation`).

---

## Session Management

Defined in `agent/core/session.py`:

- **`UserContext`** — immutable per-session: `user_id`, `company_id`, `role`, `company_slug`.
- **`SessionState`** — mutable conversation state:

| Field | Type | Purpose |
|-------|------|---------|
| `pending_draft` | `dict?` | Holds an invoice draft until confirmed/cancelled |
| `pending_line_item` | `dict?` | Holds a line-item addition until confirmed/cancelled |
| `pending_transcript` | `str?` | Original transcript to prepend when resuming |
| `pending_disambiguation` | `dict?` | Stashed fuzzy candidate + original intent for disambiguation |
| `pending_confirmation` | `bool` | Flags that a confirm/cancel is expected |
| `pending_resolved_client` | `dict?` | Holds the resolved client during multi-step invoice creation |
| `awaiting_field` | `str?` | Which field the user needs to supply (`unit_price`, `invoice_number`, `client_name`, `product_name`) |
| `awaiting_intent` | `Any?` | The full intent object being built incrementally |
| `awaiting_article_indices` | `list[int]?` | Which articles in a `create_invoice` are missing prices |
| `last_intent` | `str?` | Tracks the last intent type for context |

**User context resolution** (`agent/core/user_context.py`):

`build_session_for_user(user_id)` loads the user and company from the mock database and constructs a `SessionState` with the appropriate `UserContext`. This is called both by the CLI REPL (on user selection) and by the LiveKit agent (when a participant joins a room).

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

The `server/` directory contains a **FastAPI** application that exposes:

| File | Role |
|------|------|
| `server/main.py` | App factory — mounts routers, configures CORS (allows all origins), and exposes `GET /health` |
| `server/auth.py` | JWT authentication dependency — decodes SaaS JWTs, resolves company slug, returns `AuthenticatedUser` |
| `server/livekit_token.py` | `POST /livekit/token` — generates LiveKit room tokens with embedded user metadata |
| `server/dev_token.py` | Dev-only CLI script — prints a signed SaaS JWT for one of the 3 mock users |

---

## Background Warm-Up

Defined in `agent/core/warmup.py`:

At startup (both CLI REPL and LiveKit agent), a **daemon thread** is spawned that:

1. Loads the sentence-transformer model.
2. For each company in the mock DB, ensures Qdrant indexes exist for clients and products.

If warm-up fails (e.g., Qdrant is unreachable), a warning is logged but the application continues — the first semantic search lookup will just be slower.

---