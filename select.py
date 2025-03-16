import logging
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.select import PLATFORM_SCHEMA, SelectEntity
from homeassistant.const import CONF_HOST, CONF_API_KEY
from homeassistant.helpers import config_validation as cv

from . import DOMAIN  # Import DOMAIN from __init__.py

_LOGGER = logging.getLogger(__name__)

CONF_CHARGER_ID = "charger_id"
CONF_CHARGER_POSITION = "charger_position"
CONF_MODES = "modes"
DEFAULT_MODES = ["NORMAL", "SMART", "PAUSED"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_CHARGER_ID): cv.positive_int,
        vol.Required(CONF_CHARGER_POSITION): cv.positive_int,
        vol.Optional(CONF_MODES, default=DEFAULT_MODES): vol.All(cv.ensure_list, [cv.string]),
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("Setting up CarCharger select entity")
    """Set up the charger select entity."""
    host = config[CONF_HOST]
    api_key = config[CONF_API_KEY]
    charger_id = config[CONF_CHARGER_ID]
    charger_position = config[CONF_CHARGER_POSITION]
    modes = config.get(CONF_MODES, DEFAULT_MODES)

    _LOGGER.info("Host: %s, API Key: %s, Charger ID: %d, Charger Position: %d, Modes: %s",
                 host, api_key, charger_id, charger_position, modes)

    async_add_entities([CarChargerSelect(host, api_key, modes, charger_id, charger_position)], True)

class CarChargerSelect(SelectEntity):
    """Representation of the car charger select entity."""

    def __init__(self, host, api_key, modes, charger_id, charger_position):
        _LOGGER.info("Initializing CarChargerSelect entity")
        self._host = host
        self._api_key = api_key
        self._attr_options = modes
        self._charger_id = charger_id
        self._charger_position = charger_position
        self._attr_current_option = modes[0]  # Default to first mode
        self._attr_name = f"Charger {charger_id} Position {charger_position}"
        self._attr_unique_id = f"car_charger_{charger_id}_position_{charger_position}"

    async def async_select_option(self, option: str):
        """Set the charge mode."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid charge mode: %s", option)
            return
        url = f"https://{self._host}/chargingstations/{self._charger_id}/connectors/{self._charger_position}/mode"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"mode": option}

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.put(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            self._attr_current_option = option
                            self.async_write_ha_state()
                            _LOGGER.info("Successfully set charge mode to: %s", option)
                        else:
                            _LOGGER.error("Failed to set charge mode: %s", await response.text())
                            _LOGGER.error("Failed to set charge mode: %s", response.status)
        except Exception as e:
            _LOGGER.error("Error setting charge mode: %s", e)