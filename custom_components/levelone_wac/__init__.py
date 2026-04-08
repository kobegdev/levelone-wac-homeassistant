"""LevelOne WAC Controller integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import LevelOneWACApi
from .const import (
    CONF_AP_PASSWORD,
    CONF_AP_USERNAME,
    CONF_HOST,
    CONF_LOG_RETENTION_DAYS,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import LevelOneWACCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LevelOne WAC from a config entry."""
    controller_api = LevelOneWACApi(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    if not await controller_api.login():
        await controller_api.close()
        return False

    coordinator = LevelOneWACCoordinator(
        hass,
        controller_api,
        entry.data.get(CONF_AP_USERNAME, "admin"),
        entry.data.get(CONF_AP_PASSWORD, "admin"),
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        entry.data.get(CONF_LOG_RETENTION_DAYS, DEFAULT_LOG_RETENTION_DAYS),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: LevelOneWACCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
    return unload_ok
