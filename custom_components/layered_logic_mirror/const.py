"""Constants for the Layered Logic Mirror integration."""

from __future__ import annotations

DOMAIN = "layered_logic_mirror"

# Config-entry / discovery keys.
CONF_HOST = "host"
CONF_SECRET = "secret"  # paired-mode shared secret; empty/absent = open mode
CONF_ID = "id"  # 6-hex MAC suffix, the device's stable unique id
CONF_NAME = "name"

# mDNS service the firmware advertises (Firmware/v1/core/ll_mdns/ll_mdns.c).
ZEROCONF_SERVICE = "_layeredlogic._tcp.local."
PRODUCT = "layered-logic-mirror"

# Built-in pattern ids — must match the firmware pattern table
# (Firmware/v1/core/pattern_interp/patterns.c) and docs/control-protocol-spec.md §6.1.
PATTERNS = [
    "solid",
    "rainbow",
    "scanner",
    "spinner",
    "random",
    "breathing",
    "twinkle",
]

# Device brightness is 0-100 (control-protocol-spec §5); HA uses 0-255.
DEVICE_BRIGHTNESS_MAX = 100

# Networking timeouts (seconds).
INFO_TIMEOUT = 5  # GET /api/info during config flow
REQUEST_TIMEOUT = 5  # per WS op, mirrors App/v1/src/ws-client.ts REQ_TIMEOUT_MS
RECONNECT_MIN = 1
RECONNECT_MAX = 8

MANUFACTURER = "Layered Logic"
MODEL = "Infinity Mirror"
