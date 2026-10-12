"""Identity signals for linked account detection — see docs/linked-account-detection-spec.md (section 4).

Each signal is stored as HMAC-SHA256(IDENTITY_HASH_SECRET, "type:normalized value"), never the raw value
(PDPA). A plain hash of a phone number could be reversed by trying every number; without the server's key
it can't. The same value always gives the same hash, so "who else used this?" is an index lookup.

  normalize_email / normalize_promptpay / normalize_bank_account  -> the value two accounts must share
  record_signal(db, user, type, value)                             -> upsert one signal
  record_request_signals(db, user, request)                        -> device id (+ IP) of an HTTP request

Only creator accounts are recorded: the account graph is about who gets paid (spec D18), so a brand and
a creator account of the same person are never linked.

Routes take the request as their LAST parameter, `request: Request = None`: FastAPI always injects it, and
tests that call the route function directly can leave it out (FastAPI rejects `Request | None`).

Callers manage their own db.commit(); this module only flushes.
"""

import hashlib
import hmac
import re
import uuid

from fastapi import Request
from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import IdentitySignal, SignalType
from app.models.user import User, UserRole

DEVICE_ID_HEADER = "X-Device-Id"
_GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


# --- Normalize: different spellings of the same value must become one string ---


def normalize_email(email: str) -> str:
    """Gmail ignores dots and anything after "+" in the local part, and googlemail.com is gmail.com:
    T.O.N+shorts@gmail.com -> ton@gmail.com. Other providers may treat them as different mailboxes,
    so they are only lowercased."""
    email = email.strip().lower()
    local, at, domain = email.rpartition("@")
    if not at:
        return email
    if domain in _GMAIL_DOMAINS:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def normalize_promptpay(promptpay_id: str) -> str:
    """Phone number -> +66XXXXXXXXX, national id / tax id -> 13 digits. Raises ValueError otherwise."""
    digits = re.sub(r"\D", "", promptpay_id)
    if len(digits) == 10 and digits.startswith("0"):
        return "+66" + digits[1:]
    if len(digits) == 11 and digits.startswith("66"):
        return "+" + digits
    if len(digits) == 13:
        return digits
    raise ValueError("PromptPay ID must be a 10-digit phone number or a 13-digit ID number")


def normalize_bank_account(bank_code: str, account_number: str) -> str:
    """-> "BANKCODE:digits", e.g. ("kbank", "123-4-56789-0") -> "KBANK:1234567890"."""
    digits = re.sub(r"\D", "", account_number)
    return f"{bank_code.strip().upper()}:{digits}"


def hash_signal(signal_type: SignalType, normalized: str) -> str:
    message = f"{signal_type.value}:{normalized}".encode()
    return hmac.new(settings.identity_hash_secret.encode(), message, hashlib.sha256).hexdigest()


# --- Record ---


def record_signal(db: Session, user: User, signal_type: SignalType, normalized: str | None) -> bool:
    """Store that `user` used this value. Returns True if it is new for this user.

    Seen before -> only last_seen_at moves. Old values are kept (e.g. a previous payout account) so
    switching to another value can't undo a link.
    """
    if user.role != UserRole.creator or not normalized:
        return False
    value_hash = hash_signal(signal_type, normalized)
    # ON CONFLICT: two requests of the same user at once (e.g. double-click) mustn't fail on the unique key.
    inserted = db.scalar(
        insert(IdentitySignal)
        .values(user_id=user.id, type=signal_type, value_hash=value_hash)
        .on_conflict_do_nothing(index_elements=["user_id", "type", "value_hash"])
        .returning(IdentitySignal.id)
    )
    if inserted is None:
        db.execute(
            update(IdentitySignal)
            .where(
                IdentitySignal.user_id == user.id,
                IdentitySignal.type == signal_type,
                IdentitySignal.value_hash == value_hash,
            )
            .values(last_seen_at=func.now())
        )
    db.flush()
    return inserted is not None


def device_id_from(request: Request | None) -> str | None:
    """The browser's random device id (frontend lib/api.ts). Missing or not a UUID -> None, never an error."""
    if request is None:
        return None
    try:
        return str(uuid.UUID(request.headers.get(DEVICE_ID_HEADER, "").strip()))
    except ValueError:
        return None


def client_ip(request: Request | None) -> str | None:
    """The TCP peer. X-Forwarded-For is not trusted: there is no reverse proxy in front of the API yet,
    so anybody could set it. Revisit when one is added for the deploy."""
    if request is None or request.client is None:
        return None
    return request.client.host


def record_request_signals(db: Session, user: User, request: Request | None, *, ip: bool = True) -> None:
    """Device id and (unless ip=False) IP of the request that `user` just made."""
    record_signal(db, user, SignalType.device_id, device_id_from(request))
    if ip:
        record_signal(db, user, SignalType.ip, client_ip(request))
