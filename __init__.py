import logging
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.storage import Store
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the car charger integration."""
    _LOGGER.info("Setting up CarCharger integration")
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]['store'] = Store(hass, 1, f"{DOMAIN}_token")
    return True

async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up the car charger from a config entry."""
    for platform in ["select", "number"]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True