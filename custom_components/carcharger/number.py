# number.py
import logging
import aiohttp
import async_timeout
from homeassistant.components.number import NumberEntity, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, PERCENTAGE
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from . import DOMAIN
from .select import (
    CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_USERNAME, CONF_PASSWORD,
    CONF_CHARGER_ID, CONF_CHARGER_POSITION
)

_LOGGER = logging.getLogger(__name__)

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
    """Set up the charger percentage limit entity."""
    _LOGGER.info("Setting up CarCharger percentage limit entity")

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

    async_add_entities([
        ChargerPercentageLimit(
            hass, host, charger_id, charger_position, auth_manager
        )
    ], True)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up from a config entry."""
    host = config_entry.data.get("host")
    charger_id = config_entry.data.get("charger_id")
    charger_position = config_entry.data.get("charger_position")

    auth_manager = hass.data[DOMAIN]['auth_manager']

    async_add_entities([
        ChargerPercentageLimit(
            hass, host, charger_id, charger_position, auth_manager
        )
    ], True)

    return True

class ChargerPercentageLimit(NumberEntity):
    """Representation of the car charger percentage limit entity."""

    def __init__(self, hass, host, charger_id, charger_position, auth_manager):
        """Initialize the entity."""
        _LOGGER.info("Initializing ChargerPercentageLimit entity")
        self.hass = hass
        self._host = host
        self._charger_id = charger_id
        self._charger_position = charger_position
        self._auth_manager = auth_manager
        self._attr_name = f"Car Charger {charger_id} Charge Limit"
        self._attr_unique_id = f"car_charger_{charger_id}_position_{charger_position}_limit"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_value = 80  # Default value
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:battery-charging"

    async def async_set_native_value(self, value):
        access_token = await self._auth_manager.get_access_token()

        if not access_token:
            _LOGGER.error("Failed to get access token")
            return

        url = f"https://{self._host}/v3/chargingstations/{self._charger_id}/connectors/{self._charger_position}/mode"
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {"mode": "NORMAL", "limit": {"unit": "PERCENTAGE", "value": value}}

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.put(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
                            _LOGGER.info("Successfully set charging limit to: %s%%", value)
                        elif response.status == 401:
                            _LOGGER.info("Authorization failed, attempting to refresh token")
                            if await self._auth_manager.refresh_access_token():
                                # Try again with new token
                                await self.async_set_native_value(value)
                        else:
                            _LOGGER.error("Failed to set charging limit: %s (Status: %s)",
                                          await response.text(), response.status)
        except Exception as e:
            _LOGGER.error("Error setting charging limit: %s", e)

## NOT WORKING AS OF NOW
    async def async_update(self):
        """Update charging limit value from API."""
        access_token = await self._auth_manager.get_access_token()

        if not access_token:
            _LOGGER.error("Failed to get access token for update")
            return

        url = f"https://{self._host}/v3/chargingstations/{self._charger_id}/connectors/{self._charger_position}/status"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Extract the charge limit percentage if available
                            if "charge_limit_percentage" in data:
                                self._attr_native_value = data["charge_limit_percentage"]
                        elif response.status == 401:
                            await self._auth_manager.refresh_access_token()
        except Exception as e:
            _LOGGER.error("Error updating charge limit: %s", e)