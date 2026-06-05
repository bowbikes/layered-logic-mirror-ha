"""Wire protocol helpers for the Layered Logic mirror.

Ports the framing in App/v1/src/ws-client.ts (`frameFor`) and the HMAC in
App/v1/src/hmac.ts so the device's auth_logic.c verifier agrees byte-for-byte.
See docs/control-protocol-spec.md §3.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any


def new_req_id() -> str:
    """Client-generated UUID the device echoes back for correlation."""
    return str(uuid.uuid4())


def now_epoch_seconds() -> int:
    """Monotonic-ish counter; epoch seconds, per spec §3.1 (`ts`)."""
    return int(time.time())


def build_envelope(op: str, payload: Any | None = None) -> dict[str, Any]:
    """Build a request envelope.

    Key order is fixed (op, req_id, ts, payload) so the serialized prefix the
    HMAC covers is reproducible — see `frame_for`.
    """
    envelope: dict[str, Any] = {
        "op": op,
        "req_id": new_req_id(),
        "ts": now_epoch_seconds(),
    }
    if payload is not None:
        envelope["payload"] = payload
    return envelope


def _dumps(envelope: dict[str, Any]) -> str:
    # Compact separators match JS JSON.stringify (no spaces); ensure_ascii=False
    # so non-ASCII (e.g. a device name) is emitted as UTF-8 like the JS client,
    # which is what the device HMACs.
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False)


def hmac_sha256_hex(secret: str, message: str) -> str:
    """Lowercase-hex HMAC-SHA256 of UTF-8 `message` keyed on UTF-8 `secret`."""
    return hmac.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def frame_for(envelope: dict[str, Any], secret: str | None) -> str:
    """Serialize an envelope to the exact text frame sent on the wire.

    Open mode: the plain JSON. Paired mode: the signed region is the JSON minus
    its trailing ``}``; the device HMACs that exact prefix and we append
    ``,"hmac":"<mac>"}``. Mirrors ws-client.ts:frameFor.
    """
    body = _dumps(envelope)
    if not secret:
        return body
    region = body[:-1]  # drop the trailing '}'
    mac = hmac_sha256_hex(secret, region)
    return f'{region},"hmac":"{mac}"}}'
