# Bintec OSDx — Home Assistant integration

Presence detection and health monitoring for **bintec-elmeg OSDx** access points
(e.g. **W2044ax** / *Wanda Wave 2*), straight from the AP's own WLAN association
table — no SSH, no SNMP, no changes on the AP. You just enter the same
**host + username + password** you use for the web GUI.

Because the data comes from the AP that actually serves the Wi‑Fi, presence is
**reliable and doesn't flap** the way ARP‑ping based router trackers do on
Wi‑Fi‑less gateways.

## What you get

- **`device_tracker`** per associated Wi‑Fi client (associated → `home`).
  Attributes: `rssi`, `vap` (the SSID/VAP interface), `uptime`, and client IP.
  Assign these to HA **persons** for presence.
- **Sensors**: connected‑client count, CPU usage %, memory usage %, uptime,
  firmware version. (Per‑radio channel/client counts are exposed as attributes.)
- A **device** for the AP with model / firmware / serial.

## Install

### HACS (recommended)
1. HACS → ⋮ → *Custom repositories* → add `https://github.com/zonya/bintec_osdx`
   as an **Integration**.
2. Install **Bintec OSDx**, restart Home Assistant.
3. *Settings → Devices & Services → Add Integration → Bintec OSDx*.
4. Enter the AP IP, username (`admin`) and password.

### Manual
Copy `custom_components/bintec_osdx` into your HA `config/custom_components/`
and restart.

## How it works

The OSDx web GUI authenticates with client‑side `sha512crypt`
(`sha512crypt(sha512crypt(password, adminSalt), randomSalt)`); the integration
reproduces this, then reads the `wlan_mon_vss` (stations) and `index` (status)
pages over HTTP, threading the rolling `SharedTmpSid` token between requests.

## Known limitations

- The GUI is screen‑scraped, so a **major firmware UI change could break parsing**.
  Verified against **OSDx v3.6.1.2**.
- The default stations view returns the **5 GHz radio**; a follow‑up will also
  poll the 2.4 GHz radio so 2.4 GHz‑only clients are tracked.
- No temperature sensor — OSDx APs don't report it.
- Phones use **per‑network randomized MACs**; map each device while it's on your
  home Wi‑Fi.

## Disclaimer

Community project, not affiliated with bintec‑elmeg / Teldat. Use on equipment
you own/administer.
