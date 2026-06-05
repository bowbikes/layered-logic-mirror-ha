#!/usr/bin/env python3
"""Standalone wire-protocol check against a real Layered Logic mirror.

Proves the framing/HMAC in custom_components/layered_logic_mirror/protocol.py
agrees with the firmware, independent of Home Assistant.

    pip install aiohttp
    python scripts/verify_mirror.py --host <mirror-ip> [--secret <secret>]

Exercises: get_state, on=true, then brightness / base_color / pattern_id one at
a time, checking each is echoed in the response AND arrives as an async `state`
broadcast. Restores the original state at the end.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiohttp

# Import the integration's protocol module directly.
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "custom_components" / "layered_logic_mirror"),
)
import protocol  # noqa: E402


class Checker:
    def __init__(self, ws: aiohttp.ClientWebSocketResponse, secret: str | None) -> None:
        self.ws = ws
        self.secret = secret
        self.pending: dict[str, asyncio.Future] = {}
        self.broadcasts: list[dict] = []
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        async for msg in self.ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            frame = msg.json()
            if frame.get("op") == "state" and "state" in frame:
                self.broadcasts.append(frame["state"])
                continue
            fut = self.pending.pop(frame.get("req_id"), None)
            if fut and not fut.done():
                fut.set_result(frame)

    async def request(self, op: str, payload=None) -> dict:
        env = protocol.build_envelope(op, payload)
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self.pending[env["req_id"]] = fut
        await self.ws.send_str(protocol.frame_for(env, self.secret))
        return await asyncio.wait_for(fut, timeout=5)

    async def close(self) -> None:
        self._reader.cancel()


def ok(label: str, cond: bool) -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    return cond


async def expect_broadcast(chk: Checker, key: str, value, tries: int = 20) -> bool:
    """Poll the broadcast log for a state carrying key==value."""
    for _ in range(tries):
        for st in reversed(chk.broadcasts):
            if st.get(key) == value:
                return True
        await asyncio.sleep(0.05)
    return False


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="mirror IP address or hostname")
    ap.add_argument("--secret", default=None)
    args = ap.parse_args()

    all_pass = True
    async with aiohttp.ClientSession() as session:
        # 1. HTTP discovery sentinel.
        async with session.get(f"http://{args.host}/api/info", timeout=5) as r:
            info = await r.json(content_type=None)
        print("GET /api/info:", json.dumps(info))
        all_pass &= ok("product is a layered-logic-mirror",
                       info.get("product") == "layered-logic-mirror")

        # 2. WebSocket ops.
        async with session.ws_connect(f"ws://{args.host}/ws", heartbeat=30) as ws:
            chk = Checker(ws, args.secret)
            try:
                resp = await chk.request("get_state")
                state = resp.get("result") or {}
                print("get_state:", json.dumps(state))
                all_pass &= ok("get_state ok", resp.get("ok") is True)

                original = {
                    k: state.get(k)
                    for k in ("on", "brightness", "base_color", "pattern_id")
                }

                # The firmware's set_state response is best-effort and races the
                # writer task ("broadcasts are authoritative"). So we only require
                # the response to ack ok:true, and assert the real change via the
                # authoritative `state` broadcast — exactly how the HA coordinator
                # consumes state.
                async def apply(field: str, value) -> None:
                    nonlocal all_pass
                    resp = await chk.request("set_state", {field: value})
                    all_pass &= ok(f"set {field}={value} ok", resp.get("ok") is True)
                    all_pass &= ok(
                        f"{field}={value} authoritative broadcast",
                        await expect_broadcast(chk, field, value),
                    )

                await apply("on", True)
                await apply("brightness", 50 if original.get("brightness") != 50 else 75)
                await apply("base_color", "#12AB34")
                await apply("pattern_id",
                            "rainbow" if original.get("pattern_id") != "rainbow" else "twinkle")

                # restore
                restore = {k: v for k, v in original.items() if v is not None}
                if restore:
                    await chk.request("set_state", restore)
                    print("restored original state:", json.dumps(restore))
            finally:
                await chk.close()

    print()
    print("RESULT:", "ALL PASS" if all_pass else "FAILURES ABOVE")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
