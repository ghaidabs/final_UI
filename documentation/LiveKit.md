# LiveKit Integration Layer

## Overview

LiveKit provides the real-time transport layer — it handles WebRTC connections, audio track routing, and room management. The InVoice Agent plugs into LiveKit as an **agent worker** that:

1. Subscribes to incoming audio tracks from participants.
2. Pipes the audio through Deepgram STT → NLU → Dispatcher.
3. Sends the response back as a synthesized audio track (ElevenLabs TTS).
4. Optionally pushes structured JSON data over the room's data channel.

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
│  │          │   (JSON responses)    │                               │   │
│  └──────────┘                       └───────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Token Server — `server/livekit_token.py`

**Endpoint:** `POST /livekit/token`  
**Auth:** Requires `Authorization: Bearer <SaaS_JWT>` header.

This endpoint is responsible for:

- **Authenticating the user** — validates the SaaS JWT (signed with `SAAS_JWT_SECRET`, algorithm HS256) and extracts user claims (`id`, `company_id`, `role`, `email`).
- **Creating a room name** — format: `invoice-agent-{company_slug}-{user_id}-{random_hex}`. Each session gets a unique room.
- **Issuing a LiveKit access token** — signed with `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`, granting the user permission to join the room, publish audio, subscribe to tracks, and publish data.
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

The token server sits behind JWT authentication that simulates the SaaS platform's auth layer.

**Required JWT claims:**

| Claim        | Type   | Description                          |
|--------------|--------|--------------------------------------|
| `id`         | `int`  | User ID in the SaaS platform         |
| `company_id` | `int`  | Company the user belongs to          |
| `role`       | `str`  | User role (`ADMIN`, `OWNER`, etc.)   |
| `email`      | `str`  | User email (optional)                |

**Company resolution:** After decoding the JWT, the auth layer looks up the `company_id` in the mock database to resolve the company slug. If the company doesn't exist, the request is rejected with 401.

---

### 3. Agent Worker — `agent/livekit_agent.py`

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
- Registers two event handlers:
  - **`track_subscribed`** — fires when a participant publishes an audio track. The agent creates a `ParticipantVoiceHandler` for that participant.
  - **`participant_disconnected`** — fires when a participant leaves. The agent stops the handler and cleans up resources.

#### User resolution

When a new audio track arrives, the agent needs to map the LiveKit participant to an application user. Two strategies:

1. **Metadata** — the participant's metadata field contains a JSON blob with `user_id`, set by the token server. The agent parses this.
2. **Identity fallback** — if metadata is missing, the agent extracts the user ID from the participant identity string (`user-{id}`).

The resolved `user_id` is passed to `build_session_for_user()` which loads the user's company context from the mock database.

#### `ParticipantVoiceHandler`

One handler is created per participant. It manages the full voice session lifecycle:

**Key fields:**

| Field            | Type                  | Purpose                                        |
|------------------|-----------------------|------------------------------------------------|
| `_stt`           | `STTSession`          | Deepgram streaming session                     |
| `_audio_bridge`  | `LiveKitAudioSource`  | Bridges LiveKit's `AudioStream` → STT          |
| `_tts`           | `TTSSession`          | ElevenLabs synthesis session                   |
| `_out_source`    | `rtc.AudioSource`     | LiveKit audio source for agent output          |
| `_out_track`     | `rtc.LocalAudioTrack` | Published track named `"assistant-voice"`      |
| `_reply_lock`    | `asyncio.Lock`        | Prevents concurrent replies                    |
| `_agent_speaking`| `bool`                | Barge-in guard — drops transcripts during TTS  |
| `_session`       | `SessionState`        | Conversation state (drafts, disambiguation...) |

#### Audio flow — inbound

1. `start()` is called with the participant's audio track.
2. An `rtc.AudioStream` wraps the track, resampled to **16 kHz mono**.
3. `LiveKitAudioSource` reads frames from the LiveKit audio stream and feeds them to `STTSession.send_audio()`.
4. When Deepgram produces a final transcript, `_on_transcript()` fires.

#### Transcript processing

```python
async def _on_transcript(self, result: TranscriptResult) -> None:
```

1. **Barge-in guard:** if `_agent_speaking` is `True`, the transcript is dropped. This prevents the agent's own TTS output from being re-transcribed and triggering loops.
2. **Reply lock:** ensures only one transcript is processed at a time.
3. **Low-confidence annotation:** `annotate_low_confidence(result)` marks uncertain words with `⚠` so the LLM can factor in STT uncertainty.
4. **Pipeline execution:** `run_turn()` runs the full NLU → Dispatcher pipeline and returns a `VoiceResponse`.
5. **Output:** the response is sent through two channels simultaneously:
   - `_speak()` — synthesizes the spoken text and plays it into the room.
   - `_publish_text()` — pushes structured JSON over the data channel.

#### Audio flow — outbound (TTS)

```python
async def _speak(self, text: str, language: str) -> None:
```

1. Sets `_agent_speaking = True` to activate the barge-in guard.
2. Synthesizes audio via `TTSSession.synthesize()` (runs in a thread to avoid blocking the event loop).
3. The PCM bytes are chunked into **20 ms frames** at **24 kHz, 16-bit mono**.
4. Each frame is wrapped in an `rtc.AudioFrame` and captured into `_out_source`.
5. LiveKit streams these frames to all subscribers in the room as the `"assistant-voice"` track.

**Audio parameters:**

| Parameter         | Value  |
|-------------------|--------|
| Sample rate       | 24 kHz |
| Channels          | 1 (mono) |
| Bit depth         | 16-bit |
| Frame duration    | 20 ms  |
| Bytes per frame   | 960    |

#### Data channel output

```python
async def _publish_text(self, resp, language: str) -> None:
```

Publishes a JSON payload to the room's data channel (reliable mode). This allows a frontend UI to display text alongside the spoken audio.

**Payload schema:**

```json
{
  "display_text": "Facture ACME_F202607-004 créée avec succès.",
  "success": true,
  "requires_confirmation": false,
  "clarification_question": null,
  "error": null,
  "display_data": null,
  "language": "fr"
}
```

---

## Session & Multi-Tenancy

Each participant gets their own `SessionState` instance, which holds:

- **User context** — `user_id`, `company_id`, `role`, `company_slug` (from JWT metadata).
- **Conversation state** — pending drafts, disambiguation flows, awaiting fields, etc.
- **API client** — a `MockSaasClient` scoped to the user's company, enforcing tenant isolation.

This means multiple users from different companies can be in simultaneous LiveKit sessions without any state leakage.

---