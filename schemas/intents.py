from pydantic import BaseModel
from typing import Literal, Optional
from enum import Enum

class IntentType(str, Enum):
    CREATE_INVOICE     = "create_invoice"
    LOOKUP_CLIENT      = "lookup_client"
    CHECK_INVOICE      = "check_invoice"
    ADD_LINE_ITEM      = "add_line_item"
    CHECK_PAYMENT      = "check_payment"
    CONFIRM            = "confirm"
    CANCEL             = "cancel"
    UNKNOWN            = "unknown"

class BaseIntent(BaseModel):
    confidence: float = 0.0
    low_confidence_fields: list[str] = []
    raw_transcript: str = ""
    language: str = "fr"

class LineItemInput(BaseModel):
    product_name: str
    quantity: float
    unit_price: Optional[float] = None
    unit: Optional[str] = None

class ConfirmIntent(BaseIntent):
    intent: Literal[IntentType.CONFIRM]

class CancelIntent(BaseIntent):
    intent: Literal[IntentType.CANCEL]

class CreateInvoiceIntent(BaseIntent):
    intent: Literal[IntentType.CREATE_INVOICE]
    client_name: str
    articles: list[LineItemInput]
    currency: str = "TND"
    is_tva_applicable: bool = False
    is_stamp_applicable: bool = False
    payment_method: Optional[str] = None
    terms_and_conditions: Optional[str] = None

class LookupClientIntent(BaseIntent):
    intent: Literal[IntentType.LOOKUP_CLIENT]
    client_name: str

class CheckInvoiceIntent(BaseIntent):
    intent: Literal[IntentType.CHECK_INVOICE]
    invoice_number: Optional[str] = None
    client_name: Optional[str] = None

class AddLineItemIntent(BaseIntent):
    intent: Literal[IntentType.ADD_LINE_ITEM]
    invoice_number: Optional[str] = None
    product_name: str
    quantity: float
    unit_price: Optional[float] = None
    unit: Optional[str] = None

class CheckPaymentIntent(BaseIntent):
    intent: Literal[IntentType.CHECK_PAYMENT]
    invoice_number: Optional[str] = None
    client_name: Optional[str] = None

class UnknownIntent(BaseIntent):
    intent: Literal[IntentType.UNKNOWN]
    raw_text: str