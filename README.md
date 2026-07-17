# InVoice Agent

A **bilingual (French / English) voice assistant** for invoicing SaaS platform.  
Users speak natural-language commands — *"Crée une facture pour Ahmed, 3 claviers à 45 dinars"* — and the agent extracts intents, resolves entities, and drives the invoicing API through a structured pipeline.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Running Locally (CLI REPL)](#running-locally-cli-repl)
- [Running with LiveKit (Real-Time Voice)](#running-with-livekit-real-time-voice)
- [Environment Variables](#environment-variables)
- [Use-Case Walkthroughs](#use-case-walkthroughs)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

---

## Getting Started

### Prerequisites

- Python 3.11+
- A Deepgram API key (for STT)
- A Groq API key (for NLU)
- An ElevenLabs API key (for TTS)
- LiveKit Cloud account **or** self-hosted LiveKit server (for real-time voice mode)
- (Optional) A Hugging Face token (`HF_TOKEN`) for gated sentence-transformer models
- (Optional) Qdrant instance (for RAG)
- (Optional) `sounddevice` + `numpy` for local microphone testing

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd InVoice-agent-main

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Fill in the required API keys (see Environment Variables below)
```

---

## Running Locally (CLI REPL)

The local REPL lets you test the full pipeline (NLU → Dispatcher → Templates → TTS) without any LiveKit infrastructure.

```bash
python -m agent.main
```

You will be prompted to select a mock user, then you can:

| Command   | Effect                                                   |
|-----------|----------------------------------------------------------|
| *(text)*  | Treated as a transcript — sent through the full pipeline |
| `voice`   | Captures one spoken utterance via microphone → pipeline  |
| `switch`  | Change the mock user mid-session                         |
| `exit`    | Quit                                                     |

---

## Running with LiveKit (Real-Time Voice)

This is the production-grade path: a LiveKit agent connects to a LiveKit room, receives real-time audio from the user, and responds with synthesized speech.

### Architecture

```
User (browser / playground)
  │  WebRTC audio
  ▼
LiveKit Server  ◄───  LiveKit Agent Worker (agent/livekit_agent.py)
  │                        │
  │                        ├─ STT  (Deepgram Nova-3)
  │                        ├─ NLU  (Groq LLM)
  │                        ├─ Dispatcher + Entity Resolution
  │                        └─ TTS  (ElevenLabs) → audio track back to room
  │
  └─ Data channel → structured JSON responses to frontend
```

### Step-by-Step: Connect & Use the Voice Agent

#### 1. Start the FastAPI token server

```bash
uvicorn server.main:app --reload --port 8000
```

This exposes `POST /livekit/token` which generates LiveKit room tokens.

#### 2. Create a SaaS JWT (authentication token)

The token server expects an `Authorization: Bearer <JWT>` header. The JWT must be signed with your `SAAS_JWT_SECRET` and contain these claims:

```json
{
  "id": 1,
  "company_id": 1,
  "role": "ADMIN",
  "email": "admin@acme.tn"
}
```

**How to generate a SaaS JWT:**

```python
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

token = jwt.encode(
    {
        "id": 1,
        "company_id": 1,
        "role": "ADMIN",
        "email": "admin@acme.tn",
    },
    os.environ["SAAS_JWT_SECRET"],
    algorithm="HS256",
)
print(token)
```

Or manually at [jwt.io](https://jwt.io) — set algorithm to HS256, paste the payload claims, and use your `SAAS_JWT_SECRET` as the signing secret.

#### 3. Get a LiveKit room token

Use Postman (or `curl`) to call the token endpoint:

```bash
curl -X POST http://localhost:8000/livekit/token \
  -H "Authorization: Bearer <YOUR_SAAS_JWT>" \
  -H "Content-Type: application/json"
```

The response will contain:

```json
{
  "url": "wss://your-livekit-instance.livekit.cloud",
  "token": "<LIVEKIT_ROOM_TOKEN>",
  "room_name": "invoice-agent-acme-1-a3b7c9d1"
}
```

#### 4. Start the LiveKit agent worker

In a separate terminal:

```bash
python -m agent.livekit_agent start
```

The agent worker registers with the LiveKit server and waits for participants to join rooms.

#### 5. Connect via the LiveKit Agents Playground

https://github.com/livekit/agents-playground

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPGRAM_API_KEY` | Deepgram API key — powers Nova-3 streaming STT |
| `GROQ_API_KEY` | Groq API key — LLM for intent extraction |
| `ELEVENLABS_API_KEY` | ElevenLabs API key — text-to-speech |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID |
| `ELEVENLABS_MODEL_ID` | ElevenLabs model ID |
| `LIVEKIT_URL` | LiveKit server URL (e.g., `wss://xxx.livekit.cloud`) |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `SAAS_JWT_SECRET` | Secret used to sign/verify SaaS JWTs |
| `HF_TOKEN` | Hugging Face token for gated embedding models |
| `QDRANT_ENDPOINT` | Qdrant server URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `SAAS_API_BASE_URL` | Production SaaS API base URL |
| `SAAS_API_TEST_TOKEN` | Test token for the SaaS API |
| `ENV` | Environment flag (`dev`, `prod`) |

---