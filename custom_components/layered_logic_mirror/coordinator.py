"""Persistent WebSocket connection to a Layered Logic mirror.

Push model (iot_class=local_push): the device broadcasts full state on every
change, so there is no polling. One long-lived task owns the socket, correlates
request/response by req_id (like App/v1/src/ws-client.ts), and feeds broadcasts
to Home Assistant via the coordinator.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    RECONNECT_MAX,
    RECONNECT_MIN,
    REQUEST_TIMEOUT,
)
from .protocol import build_envelope, frame_for

_LOGGER = logging.getLogger(__name__)


class MirrorError(Exception):
    """A device op returned ok:false or the request failed."""


class MirrorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns the WS link and exposes the latest device state to entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        host: str,
        secret: str | None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {host}",
            # No update_interval: state arrives via push broadcasts.
        )
        self._host = host
        self._secret = secret or None
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._runner: asyncio.Task[None] | None = None
        self._closing = False
        self._first_data = asyncio.Event()

    @property
    def ws_url(self) -> str:
        return f"ws://{self._host}/ws"

    async def async_start(self) -> None:
        """Start the connection runner and wait for the first state snapshot."""
        self._closing = False
        self._runner = self.config_entry.async_create_background_task(
            self.hass, self._run(), name=f"{DOMAIN}-{self._host}-ws"
        )
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT * 2):
                await self._first_data.wait()
        except TimeoutError as err:
            await self.async_shutdown()
            raise TimeoutError(f"no response from mirror at {self._host}") from err

    async def async_shutdown(self) -> None:
        """Tear down the runner and socket."""
        self._closing = True
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        if self._runner is not None:
            self._runner.cancel()
            try:
                await self._runner
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def _run(self) -> None:
        """Connection loop: connect, drain frames, reconnect with backoff."""
        backoff = RECONNECT_MIN
        while not self._closing:
            try:
                async with self._session.ws_connect(
                    self.ws_url, heartbeat=30
                ) as ws:
                    self._ws = ws
                    backoff = RECONNECT_MIN
                    # The initial get_state must run *concurrently* with the read
                    # loop: its response only arrives once _read_loop is draining
                    # the socket, so awaiting it here first would deadlock until
                    # timeout ("no response"). Fire it as a task; the read loop
                    # resolves its future.
                    snapshot = asyncio.ensure_future(self._on_connected())
                    try:
                        await self._read_loop(ws)
                    finally:
                        snapshot.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 — log and retry any link error
                _LOGGER.debug("Mirror %s connection error: %s", self._host, err)
            finally:
                self._ws = None
                self._fail_pending(ConnectionError("socket closed"))

            if self._closing:
                break
            # Mark unavailable while we are disconnected.
            if self.last_update_success:
                self.last_update_success = False
                self.async_update_listeners()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def _on_connected(self) -> None:
        """Snapshot state right after (re)connecting."""
        try:
            state = await self._send("get_state")
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("get_state after connect failed: %s", err)
            return
        self.async_set_updated_data(state)
        self._first_data.set()

    async def _read_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                self._dispatch(msg.json())
            elif msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                break

    def _dispatch(self, frame: dict[str, Any]) -> None:
        op = frame.get("op")
        # Unsolicited full-state broadcast (spec §3.3) — authoritative.
        if op == "state" and "state" in frame:
            self.async_set_updated_data(frame["state"])
            self._first_data.set()
            return
        # Response envelope — correlate by req_id.
        req_id = frame.get("req_id")
        fut = self._pending.pop(req_id, None) if req_id else None
        if fut is None or fut.done():
            return
        if frame.get("ok"):
            fut.set_result(frame.get("result") or {})
        else:
            error = frame.get("error") or {}
            fut.set_exception(
                MirrorError(error.get("message") or error.get("code") or "device error")
            )

    def _fail_pending(self, err: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()

    async def _send(self, op: str, payload: Any | None = None) -> dict[str, Any]:
        ws = self._ws
        if ws is None or ws.closed:
            raise ConnectionError("not connected")
        envelope = build_envelope(op, payload)
        req_id = envelope["req_id"]
        fut: asyncio.Future[dict[str, Any]] = self.hass.loop.create_future()
        self._pending[req_id] = fut
        try:
            await ws.send_str(frame_for(envelope, self._secret))
            async with asyncio.timeout(REQUEST_TIMEOUT):
                return await fut
        finally:
            self._pending.pop(req_id, None)

    async def async_set_state(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial state update; returns the device's updated state."""
        return await self._send("set_state", patch)
