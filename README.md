# Layered Logic Mirror — Home Assistant integration

[![Validate](https://github.com/bowbikes/layered-logic-mirror-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/bowbikes/layered-logic-mirror-ha/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

A custom integration that brings a Layered Logic infinity mirror into Home
Assistant as a native **dimmable RGB light with selectable effects**. It talks to
the mirror's existing firmware over its LAN WebSocket API — **no firmware changes
required**.

## What you get

A single `light` entity per mirror with:

- **On / off**
- **Brightness** (mapped to the device's 0–100 scale)
- **RGB color** (the pattern base color)
- **Effects** — the 7 built-in patterns: `solid`, `rainbow`, `scanner`,
  `spinner`, `random`, `breathing`, `twinkle`

State is **pushed** from the device (`iot_class: local_push`): change a pattern
with the physical button and Home Assistant updates instantly, no polling.

## Requirements

- Home Assistant 2024.12 or newer
- A mirror running Layered Logic V1 firmware, reachable over the network
- No Python dependencies beyond Home Assistant itself

## Install

### Via HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/bowbikes/layered-logic-mirror-ha`, category
   **Integration**.
3. Install **Layered Logic Mirror**, then restart Home Assistant.

### Manual

Copy `custom_components/layered_logic_mirror/` into your Home Assistant
`config/custom_components/` directory and restart.

## Add a mirror

**Settings → Devices & Services → Add Integration → Layered Logic Mirror.**

- **Same LAN as the mirror:** it is auto-discovered over mDNS
  (`_layeredlogic._tcp`) — just confirm it.
- **Different subnet (mDNS can't cross subnets):** enter the mirror's IP address
  manually, e.g. `192.168.1.42`.

If the mirror is in **paired mode**, enter its shared secret; otherwise leave the
secret field blank (open mode).

## How it works

The integration is a thin client over the device control protocol:

- `GET /api/info` confirms the device and reads its stable id during setup.
- A persistent WebSocket to `ws://<host>/ws` carries `get_state` / `set_state`
  ops and receives `state` broadcasts.
- Paired mode signs each frame with HMAC-SHA256, byte-compatible with the
  firmware and the Layered Logic mobile app.

> The device's `set_state` **response** is best-effort and races the firmware's
> writer task, so the integration treats the unsolicited `state` broadcast as the
> source of truth for entity state — never the command response.

## Develop / verify against a real mirror

`scripts/verify_mirror.py` is a standalone harness that exercises the wire
protocol against a real device (independent of Home Assistant):

```bash
pip install aiohttp
python scripts/verify_mirror.py --host <mirror-ip>            # open mode
python scripts/verify_mirror.py --host <mirror-ip> --secret X # paired mode
```

It checks `/api/info`, `get_state`, and `set_state` for power / brightness /
color / pattern, asserting each change via the authoritative broadcast, then
restores the original state.

CI runs Home Assistant **hassfest** and **HACS** validation on every push
(`.github/workflows/validate.yml`).

## Limitations (V1)

- Pattern upload/editing is not supported (firmware is V1-built-in only).
- OTA, Wi-Fi provisioning, and telemetry toggles are not exposed as entities.

## License

[MIT](LICENSE) © Layered Logic LLC
