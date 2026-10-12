from pydantic import BaseModel


class PlatformStatus(BaseModel):
    """One video platform as seen by the current user (drives Settings and the submit form)."""

    name: str  # "youtube"
    label: str  # "YouTube"
    account_label: str  # "YouTube channel"
    supported: bool  # accepted for submissions right now
    connected: bool  # the current user has linked an account on it
    account_name: str | None = None
