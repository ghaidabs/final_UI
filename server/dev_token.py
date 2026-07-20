# Dev-only helper: prints a signed SaaS JWT for one of the 3 mock users

import argparse
import os
import sys
import time
from pathlib import Path
import jwt
from dotenv import load_dotenv
from mock.db import get_user_by_id

load_dotenv()

SAAS_JWT_SECRET = os.environ.get("SAAS_JWT_SECRET")
SAAS_JWT_ALGORITHM = os.environ.get("SAAS_JWT_ALGORITHM")

MOCK_USERS = {
    "1": 1,  # admin@acme.tn     / ADMIN / ACME
    "2": 2,  # admin@nova.tn     / ADMIN / NOVA
    "3": 3,  # owner@platform.tn / OWNER / ACME
}


def _select_user() -> int:
    print("Select a mock user:")
    print("  1) admin@acme.tn     (ADMIN, ACME)")
    print("  2) admin@nova.tn     (ADMIN, NOVA)")
    print("  3) owner@platform.tn (OWNER, ACME)")
    choice = input("> ").strip()
    return MOCK_USERS.get(choice, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a dev SaaS JWT for a mock user.")
    parser.add_argument("--user", choices=MOCK_USERS.keys(), help="1, 2, or 3")
    args = parser.parse_args()

    if not SAAS_JWT_SECRET:
        raise SystemExit("SAAS_JWT_SECRET is not set. Add it to your .env first.")

    user_id = MOCK_USERS[args.user] if args.user else _select_user()
    user = get_user_by_id(user_id)
    if not user:
        raise SystemExit(f"No mock user with id {user_id}")

    claims = {
        "id": user["id"],
        "company_id": user["company_id"],
        "role": user["role"],
        "email": user["email"],
    }

    token = jwt.encode(claims, SAAS_JWT_SECRET, algorithm=SAAS_JWT_ALGORITHM)

    print(f"\nuser: {user['email']}  role={user['role']}  company_id={user['company_id']}")
    print(f"\n{token}\n")
    print("Try it:")
    print(
        f'  curl -s -X POST http://localhost:8000/livekit/token '
        f'-H "Authorization: Bearer {token}" | python -m json.tool'
    )


if __name__ == "__main__":
    main()