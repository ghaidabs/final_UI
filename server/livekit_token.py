import json
import os
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from livekit import api as lk_api
from server.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/livekit", tags=["livekit"])

LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")

TOKEN_TTL = timedelta(minutes=30)


class LiveKitTokenResponse(BaseModel):
    url: str
    token: str
    room_name: str


@router.post("/token", response_model=LiveKitTokenResponse)
async def create_livekit_token(user: AuthenticatedUser = Depends(get_current_user)) -> LiveKitTokenResponse:
    room_name = f"invoice-agent-{user.company_slug.lower()}-{user.user_id}-{secrets.token_hex(4)}"
    identity = f"user-{user.user_id}"

    # Metadata rides along on the participant once they join — the LiveKit
    # worker reads this to know which mock user/company to build a
    # SessionState for, without a DB round trip.
    metadata = json.dumps({
        "user_id": user.user_id,
        "company_id": user.company_id,
        "role": user.role,
        "company_slug": user.company_slug,
    })

    grants = lk_api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )

    token = (
        lk_api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(identity)
        .with_metadata(metadata)
        .with_grants(grants)
        .with_ttl(TOKEN_TTL)
        .to_jwt()
    )

    return LiveKitTokenResponse(url=LIVEKIT_URL, token=token, room_name=room_name)