"""Client for the Bintec OSDx web GUI (esi.cgi).

Reverse-engineered against bintec-elmeg OSDx W2044ax v3.6.1.2.

Auth (mirrors /js/login.js):
    h1   = sha512crypt(password, adminSalt)     # == the stored config hash
    resp = sha512crypt(h1, randomSalt)          # posted as sessionLoginHash

Session: ``userIdent`` is carried as a URL query param (no cookie). Every data
response embeds the *next* ``SharedTmpSid`` (a rolling anti-CSRF token), which
must be threaded into the following request. A data page only returns content
after an intermediate ``navigation.xml`` fetch within the same session.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time

import aiohttp
from passlib.hash import sha512_crypt

_LOGGER = logging.getLogger(__name__)

# esi.cgi pages + their required ``menu=`` argument (url-encoded quotes).
_PAGE_STATIONS = ("wlan_mon_vss.xml", "%22WlanRadio%22")
_PAGE_STATUS = ("index.xml", "%22sm_status-index%22")

_RE_ADMIN_SALT = re.compile(r"<adminSalt>([^<]+)</adminSalt>")
_RE_RANDOM_SALT = re.compile(r"<randomSalt>([^<]+)</randomSalt>")
_RE_USERIDENT = re.compile(r"userIdent=(\d+)")
_RE_TMPSID = re.compile(r"<SharedTmpSid>(\d+)</SharedTmpSid>")
_RE_TMPSID_JS = re.compile(r"_global_tmpsessionid\s*=\s*'(\d+)'")
_RE_VAP = re.compile(r"/interfaces/wlan\[(wlan\d+)\]")


class BintecOsdxError(Exception):
    """Generic communication error."""


class BintecOsdxAuthError(BintecOsdxError):
    """Authentication failed (wrong password / session rejected)."""


def _sha512crypt(key: str, salt_field: str) -> str:
    """Reproduce crypt.crypt(key, "$6$...") using passlib (3.13-safe).

    ``salt_field`` is a modular-crypt prefix like ``$6$jVoZw0t6`` or
    ``$6$rounds=5000$jVoZw0t6``.
    """
    parts = salt_field.split("$")
    rounds = 5000
    if len(parts) >= 4 and parts[2].startswith("rounds="):
        rounds = int(parts[2][len("rounds=") :])
        salt = parts[3]
    else:
        salt = parts[-1]
    # rounds=5000 (the OSDx default) makes passlib emit the standard
    # "$6$salt$hash" form (no "rounds=" field), matching the AP's crypt.
    return sha512_crypt.using(salt=salt, rounds=rounds).hash(key)


class BintecOsdxClient:
    """Minimal async client that logs in and pulls monitoring data."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._host = host
        self._base = f"http://{host}"
        self._username = username
        self._password = password
        self._uid: str | None = None
        self._tmp: str | None = None

    @property
    def host(self) -> str:
        return self._host

    async def _text(self, url: str, **kwargs) -> str:
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=15), **kwargs
            ) as resp:
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise BintecOsdxError(f"GET {url} failed: {err}") from err

    def _data_url(self, page: str, menu: str | None) -> str:
        url = f"{self._base}/esi/0.0.0.0/esi.cgi?page={page}&userIdent={self._uid}"
        if menu:
            url += f"&menu={menu}"
        url += f"&SharedTmpSid={self._tmp}&replace=inline&cacheAvoider={int(time.time() * 1000)}"
        return url

    async def _data_page(self, page: str, menu: str | None = None) -> str:
        """Fetch an inline data page and roll the SharedTmpSid forward.

        The OSDx GUI intermittently returns an empty body; retry a few times
        before giving up so a single hiccup doesn't blank all entities.
        """
        text = ""
        for attempt in range(4):
            text = await self._text(
                self._data_url(page, menu),
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            if text.strip():
                if match := _RE_TMPSID.search(text):
                    self._tmp = match.group(1)
                return text
            await asyncio.sleep(0.4)
        return text

    async def login(self) -> None:
        """Authenticate and prime the session (uid + first SharedTmpSid)."""
        page = await self._text(f"{self._base}/")
        admin = _RE_ADMIN_SALT.search(page)
        rnd = _RE_RANDOM_SALT.search(page)
        if not (admin and rnd):
            raise BintecOsdxError("Login page did not return the expected salts")

        loop = asyncio.get_running_loop()
        h1 = await loop.run_in_executor(None, _sha512crypt, self._password, admin.group(1))
        session_hash = await loop.run_in_executor(None, _sha512crypt, h1, rnd.group(1))

        form = {
            "sessionLoginName": self._username,
            "sessionLoginHash": session_hash,
            "savedTarget": "/esi/0.0.0.0/esi.cgi?page=index.xml",
            "page": "index.xml",
        }
        try:
            async with self._session.post(
                f"{self._base}/proclog.htm",
                data=form,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise BintecOsdxError(f"Login POST failed: {err}") from err

        uid = _RE_USERIDENT.search(body)
        if not uid:
            raise BintecOsdxAuthError("Login rejected (no userIdent returned)")
        self._uid = uid.group(1)

        # The index shell occasionally comes back empty; retry before treating
        # it as an auth failure (a genuinely wrong password fails every time).
        tmp = None
        for attempt in range(5):
            shell = await self._text(
                f"{self._base}/esi/0.0.0.0/esi.cgi?page=index.xml&userIdent={self._uid}"
            )
            tmp = _RE_TMPSID_JS.search(shell) or _RE_TMPSID.search(shell)
            if tmp:
                break
            await asyncio.sleep(0.5)
        if not tmp:
            raise BintecOsdxAuthError("No session token after login (check password)")
        self._tmp = tmp.group(1)

        # Required priming step — data pages return empty without it.
        await self._data_page("navigation.xml")

    async def _poll_once(self) -> dict:
        """Pull stations + status using the current session."""
        prev_tmp = self._tmp
        await self._data_page("navigation.xml")
        if self._tmp == prev_tmp:
            # AP returned login HTML (no SharedTmpSid) — session expired.
            raise BintecOsdxError("Session token stale after navigation page — session expired")
        stations_xml = await self._data_page(*_PAGE_STATIONS)
        status_xml = await self._data_page(*_PAGE_STATUS)
        if not stations_xml.strip() and not status_xml.strip():
            raise BintecOsdxError("Both data pages empty — session likely expired")
        return {
            "stations": parse_stations(stations_xml),
            "status": parse_status(status_xml),
        }

    async def async_get_data(self) -> dict:
        """Reuse existing session; re-login once on any failure."""
        if self._uid is None:
            await self.login()
        try:
            return await self._poll_once()
        except BintecOsdxError:
            self._uid = None
            self._tmp = None
            await self.login()
            return await self._poll_once()


def _prop(item: str, col: str) -> str | None:
    match = re.search(
        rf"{col}</list\.property\.name><list\.property\.value>([^<]*)", item
    )
    return match.group(1).strip() if match else None


def parse_stations(xml: str) -> dict[str, dict]:
    """Parse the wlan_mon_vss station table into {mac: {...}}."""
    stations: dict[str, dict] = {}
    for item in xml.split("<list.item>")[1:]:
        mac_match = re.search(
            r"Col_mac</list\.property\.name><list\.property\.value>"
            r"((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})",
            item,
        )
        if not mac_match:
            # Skip header/summary rows whose Col_mac isn't a real MAC.
            continue
        mac = mac_match.group(1).lower()
        signal = _prop(item, "Col_signal")
        rssi = None
        if signal and (num := re.search(r"-?\d+", signal)):
            rssi = int(num.group())
        vap = _RE_VAP.search(item)
        stations[mac] = {
            "mac": mac,
            "ip": _prop(item, "Col_addr"),
            "rssi": rssi,
            "uptime": _prop(item, "Col_uptime"),
            "vap": vap.group(1) if vap else None,
        }
    return stations


def parse_status(xml: str) -> dict:
    """Best-effort scrape of the Status (index) dashboard.

    The OSDx Status page is HTML-ish; these regexes are intentionally lax and
    may need tweaking across firmware versions.
    """
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))

    def grab(pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    status: dict = {
        "uptime": grab(r"Uptime\s+(\d+ Day\(s\).*?Minute\(s\))"),
        "firmware": grab(r"Firmware Version\s+(v[\d.]+)"),
        "serial": grab(r"Serial Number\s+([A-Z0-9-]+)"),
        "cpu_percent": grab(r"CPU Usage\s+(\d+)\s*%"),
        "memory": grab(r"Memory Usage\s+([\d.]+/[\d.]+ MByte)"),
        "memory_percent": grab(r"Memory Usage[^()]*\((\d+)\s*%\)"),
        "power_source": grab(r"Power Source\s+([a-z ]+?)(?:Physical|Col_)"),
    }
    for key in ("cpu_percent", "memory_percent"):
        if status[key] is not None:
            status[key] = int(status[key])

    # Per-radio: "WLAN1 ... Channel in Use 11 / 4 Clients"
    radios = []
    for radio, channel, clients in re.findall(
        r"WLAN(\d).*?Channel in Use\D*(\d+)\D*?(\d+)\s+Clients", text
    ):
        radios.append(
            {"radio": int(radio), "channel": int(channel), "clients": int(clients)}
        )
    status["radios"] = radios
    return status
