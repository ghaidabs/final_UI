from pydantic import BaseModel, model_validator
from typing import Optional, Union

class VoiceResponse(BaseModel):
    spoken_text: str                       
    success: bool = True
    error: Optional[str] = None             
    clarification_question: Optional[str] = None  
    requires_confirmation: bool = False    
    draft_payload: Optional[dict] = None    
    display_data: Optional[Union[dict, list]] = None  

    @model_validator(mode="after")
    def check_consistency(self) -> "VoiceResponse":
        if self.error and self.success:
            raise ValueError("Cannot have success=True with an error set")
        if self.draft_payload and not self.requires_confirmation:
            raise ValueError("draft_payload requires requires_confirmation=True")
        return self