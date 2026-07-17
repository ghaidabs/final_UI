from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from server.livekit_token import router as livekit_token_router

load_dotenv()

app = FastAPI(title="InVoice Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(livekit_token_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}