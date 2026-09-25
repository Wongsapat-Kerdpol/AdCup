from pydantic import BaseModel


class ConnectResponse(BaseModel):
    """The frontend sends the browser here (a plain redirect can't carry the JWT header)."""

    auth_url: str
