from mock.db import get_user_by_id, get_company_by_id
from agent.core.session import SessionState, UserContext


def build_session_for_user(user_id: int) -> SessionState:
    user_row = get_user_by_id(user_id)
    if not user_row:
        raise ValueError(f"No mock user with id {user_id}")
    company = get_company_by_id(user_row["company_id"])
    if not company:
        raise ValueError(f"No mock company with id {user_row['company_id']}")

    ctx = UserContext(
        user_id=user_row["id"],
        company_id=user_row["company_id"],
        role=user_row["role"],
        company_slug=company["slug"],
    )
    return SessionState(user=ctx)