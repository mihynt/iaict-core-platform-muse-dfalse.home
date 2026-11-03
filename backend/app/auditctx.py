"""Per-request context for audit enrichment (Bang 33) and PII (Bang 6).

The HTTP middleware in main.py captures the client IP / user agent and the
optional IAICT_PII_KEY secret into context variables; stores and route
helpers read them without threading parameters through every call site.
Outside a request (tests, scripts) the values default to None / the
process environment.
"""
import contextvars
import os

_client_info: contextvars.ContextVar = contextvars.ContextVar(
    "iaict_client_info", default=(None, None))
_pii_key: contextvars.ContextVar = contextvars.ContextVar(
    "iaict_pii_key", default=None)


def set_client_info(ip: str | None, user_agent: str | None) -> None:
    _client_info.set((ip, user_agent))


def client_ip() -> str | None:
    return _client_info.get()[0]


def user_agent() -> str | None:
    return _client_info.get()[1]


def set_pii_key(key: str | None) -> None:
    _pii_key.set(key)


def pii_key() -> str | None:
    key = _pii_key.get()
    if key:
        return key
    return os.environ.get("IAICT_PII_KEY")
