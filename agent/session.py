from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class UserContext:
    user_id: int
    company_id: int
    role: str
    company_slug: str  
    
@dataclass
class SessionState:
    user: UserContext
    pending_draft: Optional[dict] = None
    pending_line_item: Optional[dict] = None
    pending_transcript: Optional[str] = None
    pending_disambiguation: Optional[dict] = None
    pending_confirmation: bool = False 
    awaiting_field: Optional[str] = None       
    awaiting_intent: Optional[Any] = None   
    awaiting_article_indices: Optional[list[int]] = None
    last_intent: Optional[str] = None
