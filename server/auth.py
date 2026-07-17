import os
import jwt
from fastapi import Header, HTTPException, status
from mock.db import get_company_by_id

SAAS_JWT_SECRET = os.environ.get("SAAS_JWT_SECRET")
SAAS_JWT_ALGORITHM = "HS256"


class AuthenticatedUser:
    def __init__(self, user_id: int, company_id: int, role: str, company_slug: str, email: str):
        self.user_id = user_id
        self.company_id = company_id
        self.role = role
        self.company_slug = company_slug
        self.email = email


async def get_current_user(authorization: str = Header(...)) -> AuthenticatedUser:
    if not SAAS_JWT_SECRET:
        raise HTTPException(status_code=500, detail="SAAS_JWT_SECRET is not configured")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        claims = jwt.decode(token, SAAS_JWT_SECRET, algorithms=[SAAS_JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")

    try:
        user_id = int(claims["id"])
        company_id = int(claims["company_id"])
        role = claims["role"]
        email = claims.get("email", "")
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing required claims")

    company = get_company_by_id(company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unknown company_id {company_id}")

    return AuthenticatedUser(
        user_id=user_id,
        company_id=company_id,
        role=role,
        company_slug=company["slug"],
        email=email,
    )