"""Config flow for the Layered Logic Mirror integration."""

from __future__ import annotations

import logging
from asyncio import timeout as asyncio_timeout
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_HOST,
    CONF_ID,
    CONF_SECRET,
    DOMAIN,
    INFO_TIMEOUT,
    PRODUCT,
)

_LOGGER = logging.getLogger(__name__)


async def _fetch_info(hass, host: str) -> dict[str, Any]:
    """GET /api/info and confirm this host is a Layered Logic mirror.

    Returns the info payload ({product, id, name, fw_version}). Raises on any
    failure so the caller can map it to a form error.
    """
    session = aiohttp_client.async_get_clientsession(hass)
    async with asyncio_timeout(INFO_TIMEOUT):
        resp = await session.get(f"http://{host}/api/info")
        resp.raise_for_status()
        info = await resp.json(content_type=None)
    if not isinstance(info, dict) or info.get("product") != PRODUCT:
        raise ValueError("not_a_mirror")
    return info


class LayeredLogicMirrorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the mirror."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_info: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual setup: host (IP/hostname) + optional paired-mode secret."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                info = await _fetch_info(self.hass, host)
            except ValueError:
                errors["base"] = "not_a_mirror"
            except (aiohttp.ClientError, TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(info["id"])
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self._create_entry(host, info, user_input.get(CONF_SECRET))

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_SECRET): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Auto-discovery via mDNS (_layeredlogic._tcp). Same-LAN only."""
        host = discovery_info.host
        props = discovery_info.properties
        device_id = props.get("id")
        if device_id:
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        try:
            info = await _fetch_info(self.hass, host)
        except (ValueError, aiohttp.ClientError, TimeoutError, OSError):
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(info["id"])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._discovered_host = host
        self._discovered_info = info
        self.context["title_placeholders"] = {
            "name": info.get("name") or info["id"]
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered mirror; collect a secret if it's paired."""
        assert self._discovered_host and self._discovered_info
        info = self._discovered_info
        if user_input is not None:
            return self._create_entry(
                self._discovered_host, info, user_input.get(CONF_SECRET)
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_SECRET): str}),
            description_placeholders={"name": info.get("name") or info["id"]},
        )

    def _create_entry(
        self, host: str, info: dict[str, Any], secret: str | None
    ) -> ConfigFlowResult:
        title = info.get("name") or info["id"]
        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_ID: info["id"],
            "fw_version": info.get("fw_version"),
        }
        if secret:
            data[CONF_SECRET] = secret
        return self.async_create_entry(title=title, data=data)
