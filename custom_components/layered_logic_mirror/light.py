"""Light platform for the Layered Logic mirror."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ID,
    DEVICE_BRIGHTNESS_MAX,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    PATTERNS,
)
from .coordinator import MirrorCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the mirror light from a config entry."""
    coordinator: MirrorCoordinator = entry.runtime_data
    async_add_entities([MirrorLight(coordinator, entry)])


def _pct_to_ha(pct: int) -> int:
    """Device 0-100 -> HA 0-255."""
    return round(max(0, min(pct, DEVICE_BRIGHTNESS_MAX)) * 255 / DEVICE_BRIGHTNESS_MAX)


def _ha_to_pct(brightness: int) -> int:
    """HA 0-255 -> device 0-100."""
    return round(max(0, min(brightness, 255)) * DEVICE_BRIGHTNESS_MAX / 255)


def _parse_hex(color: str | None) -> tuple[int, int, int] | None:
    if not color:
        return None
    h = color.lstrip("#")
    if len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return None


class MirrorLight(CoordinatorEntity[MirrorCoordinator], LightEntity):
    """A single infinity mirror exposed as an RGB light with effects."""

    _attr_has_entity_name = True
    _attr_name = None  # the device IS the light; use the device name
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = PATTERNS

    def __init__(self, coordinator: MirrorCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        device_id = entry.data.get(CONF_ID) or entry.unique_id or entry.entry_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
            sw_version=entry.data.get("fw_version"),
        )

    @property
    def _state(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    @property
    def is_on(self) -> bool | None:
        return self._state.get("on")

    @property
    def brightness(self) -> int | None:
        pct = self._state.get("brightness")
        return _pct_to_ha(pct) if isinstance(pct, int) else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return _parse_hex(self._state.get("base_color"))

    @property
    def effect(self) -> str | None:
        return self._state.get("pattern_id")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Build a single set_state patch from whatever HA passed in."""
        patch: dict[str, Any] = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            patch["brightness"] = _ha_to_pct(kwargs[ATTR_BRIGHTNESS])
        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            patch["base_color"] = f"#{r:02X}{g:02X}{b:02X}"
        if ATTR_EFFECT in kwargs:
            patch["pattern_id"] = kwargs[ATTR_EFFECT]
        await self.coordinator.async_set_state(patch)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_state({"on": False})

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
