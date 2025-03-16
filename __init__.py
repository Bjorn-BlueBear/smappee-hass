import logging

DOMAIN = "carcharger"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the car charger integration."""
    _LOGGER.info("Setting up CarCharger integration")
    hass.data[DOMAIN] = {}
    return True

async def async_setup_entry(hass, config_entry):
    """Set up the car charger from a config entry."""
    _LOGGER.info("Setting up CarCharger entry: %s", config_entry.data)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "select")
    )
    return True