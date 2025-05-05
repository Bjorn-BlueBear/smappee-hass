import logging
import aiohttp
from aiohttp import FormData
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

    _LOGGER.info("Host: %s, Charger ID: %d, Charger Position: %d",
                 host, charger_id, charger_position)

    async_add_entities([
        ChargerPercentageLimit(
            hass, host, username, password, charger_id,
            charger_position, client_id, client_secret
        )
    ], True)

class ChargerPercentageLimit(NumberEntity):
    """Representation of the car charger percentage limit entity."""

    def __init__(self, hass, host, username, password, charger_id, charger_position, client_id, client_secret):
        _LOGGER.info("Initializing ChargerPercentageLimit entity")
        self.hass = hass
        self._host = host
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        self._charger_id = charger_id
        self._charger_position = charger_position
        self._attr_name = f"Car Charger {charger_id} Charge Limit"
        self._attr_unique_id = f"car_charger_{charger_id}_position_{charger_position}_limit"
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_value = 80  # Default value
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:battery-charging"
        self._store = hass.data[DOMAIN]['store']
        self._access_token = None
        self._refresh_token = None

        # Load the access token from storage
        self.hass.async_create_task(self._load_tokens())

    async def _load_tokens(self):
        """Load the access token from storage."""

        data = await self._store.async_load()
        if not data:
            _LOGGER.warning("No token data found in storage")
            await self._authenticate()

        if not isinstance(data, dict) or 'access_token' not in data:
            _LOGGER.error("Invalid token format in storage: %s", type(data))
            await self._authenticate()

        if not data.get('access_token'):
            _LOGGER.warning("Access token is empty or None")
            await self._authenticate()

        else:
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            _LOGGER.info("Loaded access token from storage :%s", self._access_token)

    async def _authenticate(self):
        """Authenticate with the API."""
        url = f"https://{self._host}/v3/oauth2/token"
        payload = {"grant_type": "password", "username": self._username, "password": self._password, "client_id": self._client_id, "client_secret": self._client_secret}

        formData = FormData()
        for key, value in payload.items():
            formData.add_field(key, value)

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.post(url, data=formData) as response:
                        if response.status == 200:
                            data = await response.json()
                            accessToken = data.get("access_token")
                            refreshToken = data.get("refresh_token")
                            await self._save_access_token(accessToken)
                            await self._save_refresh_token(refreshToken)
                        else:
                            _LOGGER.error("Failed to authenticate: %s", await response.text())
        except Exception as e:
            _LOGGER.error("Error authenticating: %s", e)

    async def _save_access_token(self, token):
        """Save the access token to storage."""
        self._access_token = token
        await self._store.async_save({"access_token": token})
        _LOGGER.info("Saved access token to storage")

    async def _save_refresh_token(self, token):
        """Save the refresh token to storage."""
        await self._store.async_save({"refresh_token": token})
        _LOGGER.info("Saved refresh token to storage")

    async def _refresh_access_token(self):
        """Refresh the access token."""
        url = f"https://{self._host}/v3/oauth2/token"
        payload = {"grant_type": "refresh_token", "refresh_token": self._refresh_token, "client_id": self._client_id, "client_secret": self._client_secret}

        formData = FormData()
        for key, value in payload.items():
            formData.add_field(key, value)

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.post(url, data=formData) as response:
                        if response.status == 200:
                            data = await response.json()
                            accessToken = data.get("access_token")
                            refreshToken = data.get("refresh_token")
                            await self._save_access_token(accessToken)
                            await self._save_refresh_token(refreshToken)
                            _LOGGER.info("Successfully refreshed access token")
                        else:
                            _LOGGER.error("Failed to refresh access token: %s", await response.text())
        except Exception as e:
            _LOGGER.error("Error refreshing access token: %s", e)

    async def async_set_native_value(self, value):
        """Set charging limit value."""
        _LOGGER.info("Setting charging limit to: %s%%", value)

        # Ensure we have a valid token
        await self._load_tokens()

        url = f"https://{self._host}/v3/chargingstations/{self._charger_id}/connectors/{self._charger_position}/mode"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        payload = {"mode": "NORMAL", "limit": {"unit": "PERCENTAGE", "value": value}}

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.put(url, json=payload, headers=headers) as response:
                        if response.status == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
                            _LOGGER.info("Successfully set charging limit to: %s%%", value)
                        else:
                            _LOGGER.error("Failed to set charging limit: %s (Status: %s)",
                                          await response.text(), response.status)
                            # If 401 unauthorized, we might need to refresh the token
                            if response.status == 401:
                                _LOGGER.info("Authorization failed, token might be expired")
        except Exception as e:
            _LOGGER.error("Error setting charging limit: %s", e)