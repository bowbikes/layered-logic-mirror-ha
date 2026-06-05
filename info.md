# Layered Logic Mirror

Control a Layered Logic infinity mirror from Home Assistant as a native
**dimmable RGB light with selectable effects** — talking to the mirror's
existing firmware over its LAN WebSocket API. **No firmware changes required.**

- On / off, brightness, RGB color
- 7 built-in effects: `solid`, `rainbow`, `scanner`, `spinner`, `random`,
  `breathing`, `twinkle`
- Real-time **push** state (`local_push`) — physical button presses reflect
  instantly in Home Assistant
- mDNS auto-discovery on the same LAN, or add by IP across subnets
- Optional paired-mode HMAC secret

After install, add it via **Settings → Devices & Services → Add Integration →
Layered Logic Mirror**.
