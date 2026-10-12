from pydantic import BaseModel, Field, field_validator

from app.models.user import PayoutMethod

# Thai banks a creator can be paid to (code -> name). The code is part of the stored signal "BANKCODE:digits".
THAI_BANKS = {
    "BBL": "Bangkok Bank",
    "KBANK": "Kasikornbank",
    "KTB": "Krungthai Bank",
    "SCB": "Siam Commercial Bank",
    "BAY": "Krungsri (Bank of Ayudhya)",
    "TTB": "TMBThanachart Bank",
    "GSB": "Government Savings Bank",
    "BAAC": "Bank for Agriculture and Agricultural Cooperatives",
    "GHB": "Government Housing Bank",
    "KKP": "Kiatnakin Phatra Bank",
    "CIMBT": "CIMB Thai",
    "UOBT": "UOB Thailand",
    "LHB": "LH Bank",
}


class Bank(BaseModel):
    code: str
    name: str


class PayoutAccount(BaseModel):
    """Masked, display-only. The full number is never sent back (it is only stored as a hash)."""

    method: PayoutMethod
    bank_code: str | None = None
    account_masked: str
    account_name: str


class PayoutMethodResponse(BaseModel):
    account: PayoutAccount | None  # None: not set up yet — required before the first submission
    banks: list[Bank]


class PayoutMethodUpdate(BaseModel):
    method: PayoutMethod
    promptpay_id: str | None = Field(None, max_length=30)  # method=promptpay: phone or 13-digit ID
    bank_code: str | None = Field(None, max_length=20)  # method=bank
    account_number: str | None = Field(None, max_length=30)  # method=bank
    account_name: str = Field(min_length=2, max_length=100)

    @field_validator("account_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Account name must be at least 2 characters")
        return v
