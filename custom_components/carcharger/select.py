import logging
import aiohttp
from aiohttp import FormData
import async_timeout
import voluptuous as vol

from homeassistant.components.select import PLATFORM_SCHEMA, SelectEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later

from . import DOMAIN  # Import DOMAIN from __init__.py

_LOGGER = logging.getLogger(__name__)

CONF_CHARGER_ID = "charger_id"
CONF_CHARGER_POSITION = "charger_position"
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_MODES = "modes"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CHARGER_ID): cv.positive_int,
        vol.Required(CONF_CHARGER_POSITION): cv.positive_int,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    _LOGGER.info("Setting up CarCharger select entity")
    """Set up the charger select entity."""
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    charger_id = config[CONF_CHARGER_ID]
    charger_position = config[CONF_CHARGER_POSITION]

    from .auth_helper import AuthManager

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if 'auth_manager' not in hass.data[DOMAIN]:
        auth_manager = AuthManager(
            hass, host, username, password, client_id, client_secret
        )
        hass.data[DOMAIN]['auth_manager'] = auth_manager
    else:
        auth_manager = hass.data[DOMAIN]['auth_manager']

    async_add_entities([CarChargerSelect(hass, host, charger_id, charger_position, auth_manager)], True)


    _LOGGER.info("Host: %s, Charger ID: %d, Charger Position: %d",
                 host, charger_id, charger_position)

class CarChargerSelect(SelectEntity):
    """Representation of the car charger select entity."""

    def __init__(self, hass, host, charger_id, charger_position, auth_manager):
        _LOGGER.info("Initializing CarChargerSelect entity")
        self.hass = hass
        self._host = host
        self._attr_options = ["NORMAL", "SMART", "PAUSED"]
        self._charger_id = charger_id
        self._charger_position = charger_position
        self._auth_manager = auth_manager
        self._attr_current_option = "NORMAL"
        self._attr_name = f"Car Charger {charger_id} Position {charger_position}"
        self._attr_unique_id = f"car_charger_{charger_id}_position_{charger_position}"
        self._store = hass.data[DOMAIN]['store']

    async def async_select_option(self, option: str):
        access_token = await self._auth_manager.get_access_token()

        if not access_token:
            _LOGGER.error("Failed to get access token")
            return


        if option not in self._attr_options:
            _LOGGER.error("Invalid charge mode: %s", option)
            return

        url = f"https://{self._host}/v3/chargingstations/{self._charger_id}/connectors/{self._charger_position}/mode"
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {"mode": option}
        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.put(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            self._attr_current_option = option
                            self.async_write_ha_state()
                            _LOGGER.info("Successfully set charge mode to: %s", option)
                        elif response.status == 401:
                            _LOGGER.info("Authorization failed, attempting to refresh token")
                            if await self._auth_manager.refresh_access_token():
                                # Try again with new token
                                await self.async_select_option(option)
                        else:
                            _LOGGER.error("Failed to set charge mode: %s", await response.text())
                            _LOGGER.error("Failed to set charge mode: %s", response.status)
        except Exception as e:
            _LOGGER.error("Error setting charge mode: %s", e) # type: ignore