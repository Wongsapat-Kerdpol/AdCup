"""Creator payout account (linked account detection, docs/linked-account-detection-spec.md).

  GET /api/payout-method — the creator's payout account (masked) + the list of supported banks
  PUT /api/payout-method — set / change it: PromptPay (phone or ID number) or a Thai bank account

Required before the first submission (spec D8): money leaves the campaign pool in the next payout
round after approval, so who receives it must be known before that, not at withdrawal.
The full number is stored only as an HMAC identity signal; the user row keeps a masked copy for
display. Accounts paid to the same destination are one profile (they share the cap per profile).
A previous account stays recorded, so switching accounts can't undo a link.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.identity import SignalType
from app.models.user import PayoutMethod, User, UserRole
from app.schemas.payout_method import THAI_BANKS, Bank, PayoutAccount, PayoutMethodResponse, PayoutMethodUpdate
from app.services.identity import normalize_bank_account, normalize_promptpay, record_signal
from app.services.linking import rebuild_profile_groups

router = APIRouter(prefix="/api/payout-method", tags=["payout account"])

_BANKS = [Bank(code=code, name=name) for code, name in THAI_BANKS.items()]


def _response(user: User) -> PayoutMethodResponse:
    account = None
    if user.payout_method is not None:
        account = PayoutAccount(
            method=user.payout_method,
            bank_code=user.payout_bank_code,
            account_masked=user.payout_account_masked or "",
            account_name=user.payout_account_name or "",
        )
    return PayoutMethodResponse(account=account, banks=_BANKS)


def _invalid(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.get("", response_model=PayoutMethodResponse)
def get_payout_method(user: User = Depends(require_role(UserRole.creator))):
    return _response(user)


@router.put("", response_model=PayoutMethodResponse)
def set_payout_method(
    body: PayoutMethodUpdate,
    user: User = Depends(require_role(UserRole.creator)),
    db: Session = Depends(get_db),
):
    if body.method == PayoutMethod.promptpay:
        try:
            normalized = normalize_promptpay(body.promptpay_id or "")
        except ValueError as exc:
            raise _invalid(str(exc)) from exc
        bank_code = None
    else:
        bank_code = (body.bank_code or "").strip().upper()
        if bank_code not in THAI_BANKS:
            raise _invalid("Choose a bank from the list")
        normalized = normalize_bank_account(bank_code, body.account_number or "")
        if not 10 <= len(normalized.split(":", 1)[1]) <= 12:
            raise _invalid("Account number must be 10 to 12 digits")

    user.payout_method = body.method
    user.payout_bank_code = bank_code
    user.payout_account_masked = f"••• {normalized[-4:]}"
    user.payout_account_name = body.account_name
    if record_signal(db, user, SignalType.payout_account, normalized):
        rebuild_profile_groups(db)
    db.commit()
    db.refresh(user)
    return _response(user)
