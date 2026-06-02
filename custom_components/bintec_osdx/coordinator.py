"""DataUpdateCoordinator for Bintec OSDx."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BintecOsdxAuthError, BintecOsdxClient, BintecOsdxError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class BintecOsdxCoordinator(DataUpdateCoordinator[dict]):
    """Polls the AP and exposes {'stations': {...}, 'status': {...}}."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BintecOsdxClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({client.host})",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.async_get_data()
        except BintecOsdxAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except BintecOsdxError as err:
            raise UpdateFailed(str(err)) from err
