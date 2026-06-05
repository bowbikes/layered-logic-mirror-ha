"""The Layered Logic Mirror integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_HOST, CONF_SECRET
from .coordinator import MirrorCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

type MirrorConfigEntry = ConfigEntry[MirrorCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MirrorConfigEntry) -> bool:
    """Set up Layered Logic Mirror from a config entry."""
    coordinator = MirrorCoordinator(
        hass,
        entry,
        host=entry.data[CONF_HOST],
        secret=entry.data.get(CONF_SECRET),
    )
    try:
        await coordinator.async_start()
    except (TimeoutError, OSError) as err:
        raise ConfigEntryNotReady(
            f"Mirror at {entry.data[CONF_HOST]} unreachable: {err}"
        ) from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MirrorConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
