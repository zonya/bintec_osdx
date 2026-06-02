"""Constants for the Bintec OSDx integration."""

from __future__ import annotations

DOMAIN = "bintec_osdx"

DEFAULT_USERNAME = "admin"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10

MANUFACTURER = "bintec-elmeg"

# Maps the OSDx WLAN VAP interface id (wlanXXXXX) to a human label.
# These are device-specific; the integration falls back to the raw VAP id.
# (On the reference W2044ax: wlan00000=SoulIoT 2.4G, wlan01000=SoulRiver,
#  wlan01001=SoulGuest, wlan01002=SoulTV — but names differ per AP, so we
#  only use this as a hint and expose the raw VAP id as an attribute.)
