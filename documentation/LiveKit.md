# LiveKit Integration Layer

## Overview

LiveKit provides the real-time transport layer — it handles WebRTC connections, audio track routing, and room management. The InVoice Agent plugs into LiveKit as an **agent worker** that:

1. Subscribes to incoming audio tracks from participants.
2. Pipes the audio through Deepgram STT → NLU → Dispatcher.
3. Sends the response back as a synthesized audio track (ElevenLabs TTS).
4. Pushes structured JSON events over the room's data channel for the React UI.
5. Receives user actions (confirm/cancel buttons, text input, barge-in) via the data channel.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            LiveKit Server                               │
│                                                                         │
│  ┌──────────┐     WebRTC audio      ┌───────────────────────────────┐   │
│  │  User    │ ────────────────────► │      Agent Worker             │   │
│  │ (browser │                       │   (agent/livekit_agent.py)    │   │
│  │  or app) │ ◄──────────────────── │                               │   │
│  │          │     TTS audio track   │  ┌─────┐ ┌─────┐ ┌────────┐   │   │
│  │          │                       │  │ STT │→│ NLU │→│Dispatch│   │   │
│  │          │ ◄──── data channel ── │  └─────┘ └─────┘ └────────┘   │   │
│  │          │   (JSON events)       │                               │   │
│  │          │ ────── data channel ─►│  (user actions / text input)  │   │
│  └──────────┘                       └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Token Server — `server/livekit_token.py`

**Endpoint:** `POST /livekit/token`  
**Auth:** Requires `Authorization: Bearer <SaaS_JWT>` header.

This endpoint is responsible for:

- **Authenticating the user** — validates the SaaS JWT (signed with `SAAS_JWT_SECRET`, algorithm from `SAAS_JWT_ALGORITHM`) and extracts user claims (`id`, `company_id`, `role`, `email`).
- **Creating a room name** — format: `invoice-agent-{company_slug}-{user_id}-{random_hex}`. Each session gets a unique room.
- **Issuing a LiveKit access token** — signed with `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`, granting the user permission to join the room, publish audio, subscribe to tracks, and publish data. TTL is 30 minutes.
- **Embedding user metadata** — the participant's metadata field carries a JSON blob with `user_id`, `company_id`, `role`, and `company_slug`. The agent worker reads this on the server side to build the session.

**Response schema:**

```json
{
  "url": "wss://your-instance.livekit.cloud",
  "token": "<livekit_access_token>",
  "room_name": "invoice-agent-acme-1-a3b7c9d1"
}
```

**Grants issued:**

| Grant              | Value  | Purpose                              |
|--------------------|--------|--------------------------------------|
| `room_join`        | `true` | Allow joining the specified room     |
| `room`             | *name* | Scoped to the generated room name   |
| `can_publish`      | `true` | User can send audio tracks           |
| `can_subscribe`    | `true` | User can receive agent audio         |
| `can_publish_data` | `true` | User can send data channel messages  |

---

### 2. JWT Authentication — `server/auth.py`

The token server sits behind JWT authentication that validates tokens from the SaaS platform.

**`AuthenticatedUser` fields:**

| Field          | Type   | Description                          |
|----------------|--------|--------------------------------------|
| `user_id`      | `int`  | User ID in the SaaS platform         |
| `company_id`   | `int`  | Company the user belongs to          |
| `role`         | `str`  | User role (`ADMIN`, `OWNER`, etc.)   |
| `company_slug` | `str`  | Company slug (resolved from mock DB) |
| `email`        | `str`  | User email                           |

**Required JWT claims:**

| Claim        | Type   | Description                          |
|--------------|--------|--------------------------------------|
| `id`         | `int`  | User ID in the SaaS platform         |
| `company_id` | `int`  | Company the user belongs to          |
| `role`       | `str`  | User role (`ADMIN`, `OWNER`, etc.)   |
| `email`      | `str`  | User email (optional)                |

**Company resolution:** After decoding the JWT, the auth layer looks up the `company_id` in the mock database to resolve the company slug. If the company doesn't exist, the request is rejected with 401.

---

### 3. Dev Token Generator — `server/dev_token.py`

A CLI utility for development that prints a signed SaaS JWT for testing:

```bash
# Interactive mode — prompts you to select a user
python -m server.dev_token

# Direct mode — skip the prompt
python -m server.dev_token --user 1
```

**Available mock users:**

| # | Email              | Role  | Company |
|---|--------------------|-------|---------|
| 1 | admin@acme.tn      | ADMIN | ACME    |
| 2 | admin@nova.tn      | ADMIN | NOVA    |
| 3 | owner@platform.tn  | OWNER | ACME    |

The script also prints a ready-to-use `curl` command to test the token endpoint.

---

### 4. Agent Worker — `agent/livekit_agent.py`

The agent worker is a long-running process that registers with the LiveKit server and handles voice sessions.

#### Starting the worker

```bash
python -m agent.livekit_agent start
```

This calls `livekit-agents` CLI which:
1. Connects to the LiveKit server using `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
2. Registers the `entrypoint` function as the job handler.
3. Waits for rooms to be created — when a participant joins, LiveKit dispatches a job to the worker.

#### Entrypoint (`entrypoint`)

```python
async def entrypoint(ctx: JobContext) -> None:
```

- Connects to the room with `auto_subscribe=AutoSubscribe.AUDIO_ONLY` — the agent only cares about audio tracks.
- Starts the search warm-up thread (`start_warmup_thread()`) on connection.
- Registers four event handlers:
  - **`track_subscribed`** — fires when a participant publishes an audio track. The agent creates a `ParticipantVoiceHandler` for that participant.
  - **`track_unsubscribed`** — fires when a participant's audio track is removed. The handler is told to detach the audio source.
  - **`participant_disconnected`** — fires when a participant leaves. The handler is stopped and removed from the handler map.
  - **`data_received`** — fires when the frontend sends a data channel message. Dispatches to the appropriate handler method.

#### User resolution

When a new audio track arrives, the agent needs to map the LiveKit participant to an application user. Two strategies:

1. **Metadata** — the participant's metadata field contains a JSON blob with `user_id`, set by the token server. The agent parses this.
2. **Identity fallback** — if metadata is missing, the agent extracts the user ID from the participant identity string (`user-{id}`).

The resolved `user_id` is passed to `build_session_for_user()` which loads the user's company context from the mock database.

#### Handler creation (double-checked locking)

Handlers are created lazily via `_get_or_create_handler()` which uses an `asyncio.Lock` to prevent race conditions when a participant publishes multiple tracks simultaneously. The handler is stored in a `dict[str, ParticipantVoiceHandler]` keyed by participant identity.

---

### 5. `ParticipantVoiceHandler`

One handler is created per participant. It manages the full voice session lifecycle.

**Key fields:**

| Field              | Type                  | Purpose                                        |
|--------------------|-----------------------|------------------------------------------------|
| `_stt`             | `STTSession`          | Deepgram streaming session                     |
| `_audio_bridge`    | `LiveKitAudioSource`  | Bridges LiveKit's `AudioStream` → STT          |
| `_tts`             | `TTSSession`          | ElevenLabs synthesis session                   |
| `_out_source`      | `rtc.AudioSource`     | LiveKit audio source for agent output          |
| `_out_track`       | `rtc.LocalAudioTrack` | Published track named `"assistant-voice"`      |
| `_reply_lock`      | `asyncio.Lock`        | Prevents concurrent replies                    |
| `_agent_speaking`  | `bool`                | Barge-in guard — drops transcripts during TTS  |
| `_barge_in_requested` | `bool`             | Signals TTS playback should stop early         |
| `_locked_language` | `str?`                | Locked conversation language (set on first utterance) |
| `_session`         | `SessionState`        | Conversation state (drafts, disambiguation...) |
| `_saas`            | `MockSaasClient`      | Scoped API client for this user's company      |

---

### 6. Audio Flow — Inbound

1. `attach_audio_track()` is called with the participant's audio track.
2. An `rtc.AudioStream` wraps the track, resampled to **16 kHz mono**.
3. `LiveKitAudioSource` reads frames from the LiveKit audio stream and feeds them to `STTSession.send_audio()`.
4. When Deepgram produces a final transcript, `_on_transcript()` fires.
5. A `listening_ready` event is published to the frontend.

#### Track lifecycle

- **Attach:** When a new audio track is subscribed, the handler creates or re-creates the `LiveKitAudioSource` bridge. If a previous bridge exists, it's stopped first.
- **Detach:** When a track is unsubscribed, the bridge is stopped and a `listening_ready: false` event is sent.
- **Stop:** On participant disconnect, both the bridge and STT session are torn down.

---

### 7. Transcript Processing

```python
async def _on_transcript(self, result: TranscriptResult) -> None:
```

1. **Barge-in guard:** if `_agent_speaking` is `True`, the transcript is dropped. This prevents the agent's own TTS output from being re-transcribed and triggering loops.
2. **Low-confidence annotation:** `annotate_low_confidence(result)` marks uncertain words with `⚠` so the LLM can factor in STT uncertainty.
3. **Language locking:** `_lock_language()` sets the conversation language on the first utterance and keeps it fixed for the rest of the session.
4. **Pipeline execution:** `_run_and_publish()` acquires the reply lock, echoes the transcript to the frontend, runs the full NLU → Dispatcher pipeline via `run_turn()`, and sends both text and audio responses.

---

### 8. Audio Flow — Outbound (TTS)

```python
async def _speak(self, text: str, language: str) -> None:
```

1. Sets `_agent_speaking = True` to activate the barge-in guard.
2. Publishes an `agent_speaking: true` event to the frontend.
3. Synthesizes audio via `TTSSession.synthesize()` (runs in a thread via `asyncio.to_thread` to avoid blocking the event loop).
4. The PCM bytes are chunked into **20 ms frames** at **24 kHz, 16-bit mono**.
5. Each frame is wrapped in an `rtc.AudioFrame` and captured into `_out_source`.
6. **Barge-in check:** before each frame, checks `_barge_in_requested` — if `True`, stops playback immediately.
7. LiveKit streams these frames to all subscribers in the room as the `"assistant-voice"` track.
8. Finally, sets `_agent_speaking = False` and publishes `agent_speaking: false`.

**Audio parameters:**

| Parameter         | Value  |
|-------------------|--------|
| Sample rate       | 24 kHz |
| Channels          | 1 (mono) |
| Bit depth         | 16-bit |
| Frame duration    | 20 ms  |
| Bytes per frame   | 960    |

---

### 9. Language Locking

```python
def _lock_language(self, language: Optional[str], text: Optional[str] = None) -> str:
```

The conversation language is **locked on the first utterance** for each participant:

1. First call: resolves the language via `resolve_language(tag, text)` (tries STT-detected language first, falls back to `langdetect`).
2. Stores the result in `_locked_language`.
3. All subsequent calls return the locked language regardless of input.

This prevents confusing mid-session language switches (e.g., if the user says a French word that `langdetect` misidentifies as another language).

---

### 10. Data Channel Protocol

The agent communicates with the frontend through LiveKit's **reliable data channel**. All messages are JSON-encoded.

#### Agent → Frontend (events published by the agent)

| Event Type | Fields | When |
|------------|--------|------|
| `listening_ready` | `ready: bool` | Audio track attached/detached |
| `agent_speaking` | `speaking: bool` | TTS playback starts/stops |
| `vad_state` | `speaking: bool` | Voice activity detected/ended |
| `transcript_final` | `text: str` | STT produces a final transcript |
| `processing` | `active: bool` | Pipeline processing starts/stops |
| `response` | *(see below)* | Pipeline produces a VoiceResponse |

**`response` event payload:**

```json
{
  "type": "response",
  "display_text": "Facture ACME_F202607-004 créée avec succès.",
  "success": true,
  "requires_confirmation": false,
  "clarification_question": null,
  "error": null,
  "display_data": null,
  "draft_payload": null,
  "turn_state": { ... },
  "language": "fr"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `display_text` | `str` | Text to show in the UI (falls back to `spoken_text`) |
| `success` | `bool` | Whether the action succeeded |
| `requires_confirmation` | `bool` | Whether the user needs to confirm/cancel |
| `clarification_question` | `str?` | Question to ask the user for more info |
| `error` | `str?` | Error message if the action failed |
| `display_data` | `any?` | Structured data (invoice details, client info, etc.) |
| `draft_payload` | `any?` | Invoice draft data for preview |
| `turn_state` | `dict?` | Current session state snapshot for the UI |
| `language` | `str` | Detected/locked language (`"fr"` or `"en"`) |

#### Frontend → Agent (messages sent by the UI)

| Message Type | Fields | Purpose |
|-------------|--------|---------|
| `user_action` | `action: "confirm" \| "cancel" \| "barge_in"`, `language?: str` | Button press from the UI |
| `text_input` | `text: str`, `language?: str` | Text message typed by the user |

**Barge-in:** When the user sends `{"type": "user_action", "action": "barge_in"}`, the agent sets `_barge_in_requested = True`, which causes the current TTS playback to stop at the next frame boundary.

**Button actions (confirm/cancel):** The agent constructs a `ConfirmIntent` or `CancelIntent` via `build_button_intent()` and dispatches it through the normal pipeline. This way, button presses and voice commands follow identical logic paths.

**Text input:** When the user types text instead of speaking, `handle_text_input()` runs it through the same `run_turn()` pipeline but skips the transcript echo to the frontend (since the user already sees their own text).

---

### 11. Session & Multi-Tenancy

Each participant gets their own `SessionState` instance, which holds:

- **User context** — `user_id`, `company_id`, `role`, `company_slug` (from JWT metadata).
- **Conversation state** — pending drafts, disambiguation flows, awaiting fields, etc.
- **API client** — a `MockSaasClient` scoped to the user's company, enforcing tenant isolation.

This means multiple users from different companies can be in simultaneous LiveKit sessions without any state leakage.