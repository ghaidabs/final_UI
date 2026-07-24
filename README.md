# InVoice Agent

A **bilingual (French / English) voice assistant** for an invoicing SaaS platform.  
Users speak natural-language commands — *"Crée une facture pour Ahmed, 3 claviers à 45 dinars"* — and the agent extracts intents, resolves entities, and drives the invoicing API through a structured pipeline.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Running the Full Stack (4 Terminals)](#running-the-full-stack-4-terminals)
- [Running Locally (CLI REPL)](#running-locally-cli-repl)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Documentation](#documentation)

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the UI)
- A **Deepgram** API key (STT)
- A **Groq** API key (NLU / LLM)
- An **ElevenLabs** API key (TTS)
- A **LiveKit Cloud** account or self-hosted LiveKit server
- (Optional) A Hugging Face token (`HF_TOKEN`) for gated sentence-transformer models
- (Optional) A **Qdrant** instance for vector-based entity resolution

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd InVoice-agent-main

# 2. Create a virtual environment & install Python dependencies
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3. Install frontend dependencies
cd UI
npm install
cd ..

# 4. Configure environment
cp .env.example .env          # Backend — fill in API keys
cp UI/.env.example UI/.env    # Frontend — set VITE_LIVEKIT_TOKEN_URL
```

---

## Running the Full Stack (4 Terminals)

The application requires **four processes** running in parallel:

### Terminal 1 — FastAPI Token Server

```bash
python -m uvicorn server.main:app --reload --port 8000
```

Exposes `POST /livekit/token` (LiveKit room token generation) and `GET /health`.

### Terminal 2 — LiveKit Agent Worker

```bash
python -m agent.livekit_agent start
```

Registers with the LiveKit server and handles real-time voice sessions. When a user joins a room, the worker creates a per-participant voice handler that runs the full STT → NLU → Dispatcher → TTS pipeline.

### Terminal 3 — Dev Token Generator

```bash
python -m server.dev_token
```

Interactive helper that prints a signed SaaS JWT for one of the 3 mock users. Use the printed token as the `Authorization: Bearer <token>` header when calling the token endpoint, or paste it into the UI's authentication flow.

Available mock users:

| # | Email              | Role  | Company |
|---|--------------------|-------|---------|
| 1 | admin@acme.tn      | ADMIN | ACME    |
| 2 | admin@nova.tn      | ADMIN | NOVA    |
| 3 | owner@platform.tn  | OWNER | ACME    |

You can also skip the interactive prompt: `python -m server.dev_token --user 1`

### Terminal 4 — React UI (Vite Dev Server)

```bash
cd UI
npm run dev
```

Opens the voice agent panel in your browser. The UI connects to LiveKit via WebRTC and provides voice input, text input, and button actions (confirm/cancel).

---

## Running Locally (CLI REPL)

The local REPL lets you test the full pipeline (STT → NLU → Dispatcher → Templates → TTS) without any LiveKit infrastructure or frontend:

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

> **Note:** Voice mode requires `sounddevice` and `numpy` (`pip install sounddevice numpy`).

---

## Environment Variables

### Backend (`.env` at project root)

| Variable                       | Description                                              |
|--------------------------------|----------------------------------------------------------|
| `DEEPGRAM_API_KEY`             | Deepgram API key — powers Nova-3 streaming STT           |
| `GROQ_API_KEY`                 | Groq API key — LLM for intent extraction                 |
| `ELEVENLABS_API_KEY`           | ElevenLabs API key — text-to-speech                      |
| `ELEVENLABS_VOICE_ID`          | ElevenLabs voice ID                                      |
| `ELEVENLABS_MODEL_ID`          | ElevenLabs model ID                                      |
| `LIVEKIT_URL`                  | LiveKit server URL (e.g., `wss://xxx.livekit.cloud`)     |
| `LIVEKIT_API_KEY`              | LiveKit API key                                          |
| `LIVEKIT_API_SECRET`           | LiveKit API secret                                       |
| `SAAS_JWT_SECRET`              | Secret used to sign/verify SaaS JWTs                     |
| `SAAS_JWT_ALGORITHM`           | JWT algorithm (e.g., `HS256`)                            |
| `ACCESS_TOKEN_EXPIRE_MINUTES`  | Access token TTL in minutes                              |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Refresh token TTL in minutes                             |
| `HF_TOKEN`                     | Hugging Face token for gated embedding models            |
| `QDRANT_ENDPOINT`              | Qdrant server URL                                        |
| `QDRANT_API_KEY`               | Qdrant API key                                           |
| `SAAS_API_BASE_URL`            | Production SaaS API base URL                             |
| `SAAS_API_TEST_TOKEN`          | Test token for the SaaS API                              |
| `ENV`                          | Environment flag (`dev`, `prod`)                         |

### Frontend (`UI/.env`)

| Variable                 | Description                                                      |
|--------------------------|------------------------------------------------------------------|
| `VITE_LIVEKIT_TOKEN_URL` | URL of the token endpoint (e.g., `http://localhost:8000/livekit/token`) |

---