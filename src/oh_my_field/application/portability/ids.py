import secrets
from datetime import datetime


def new_id(created_at: datetime) -> str:
    return f"{created_at:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
