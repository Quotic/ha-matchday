"""The Matchday integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MatchdayApiClient
from .api_openligadb import OpenLigaDbClient
from .const import (
    CONF_API_KEY,
    CONF_DATA_SOURCE,
    DATA_SOURCE_APIFOOTBALL,
    DATA_SOURCE_OPENLIGADB,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MatchdayCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Matchday from a config entry."""
    session = async_get_clientsession(hass)

    data_source = entry.data.get(CONF_DATA_SOURCE, DATA_SOURCE_APIFOOTBALL)

    if data_source == DATA_SOURCE_OPENLIGADB:
        api_client = OpenLigaDbClient(session)
    else:
        api_client = MatchdayApiClient(entry.data[CONF_API_KEY], session)

    coordinator = MatchdayCoordinator(hass, entry, api_client)

    # Block until the first successful refresh so entities have data on startup.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
