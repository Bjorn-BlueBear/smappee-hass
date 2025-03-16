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

    _LOGGER.info("Host: %s, Charger ID: %d, Charger Position: %d",
                 host, charger_id, charger_position)

    async_add_entities([CarChargerSelect(hass, host, username, password, charger_id, charger_position, client_id, client_secret)], True)

class CarChargerSelect(SelectEntity):
    """Representation of the car charger select entity."""

    def __init__(self, hass, host, username, password, charger_id, charger_position, client_id, client_secret):
        _LOGGER.info("Initializing CarChargerSelect entity")
        self.hass = hass
        self._host = host
        self._client_id = client_id
        self._client_secret = client_secret
        self._username = username
        self._password = password
        self._attr_options = ["NORMAL", "SMART", "PAUSED"]
        self._charger_id = charger_id
        self._charger_position = charger_position
        self._attr_current_option = "NORMAL"
        self._attr_name = f"Car Charger {charger_id} Position {charger_position}"
        self._attr_unique_id = f"car_charger_{charger_id}_position_{charger_position}"
        self._store = hass.data[DOMAIN]['store']

        # Load the access token from storage
        self.hass.async_create_task(self._load_tokens())

        # Schedule token refresh
        self.hass.async_create_task(self._schedule_token_refresh())

    async def _load_tokens(self):
        """Load the access token from storage."""
        data = await self._store.async_load()
        if data:
            self._access_token = data.get("access_token")
            self._refresh_token = data.get("refresh_token")
            _LOGGER.info("Loaded access token from storage")
        else:
            await self._authenticate()

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

    async def _schedule_token_refresh(self):
        """Schedule periodic token refresh."""
        async def refresh(_):
            await self._refresh_access_token()
            async_call_later(self.hass, 43200, refresh)

        async_call_later(self.hass, 43200, refresh)

    async def async_select_option(self, option: str):
        """Set the charge mode."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid charge mode: %s", option)
            return
        url = f"https://{self._host}/v3/chargingstations/{self._charger_id}/connectors/{self._charger_position}/mode"
        headers = {"Authorization": f"Bearer {self._access_token}"}
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
            _LOGGER.error("Error setting charge mode: %s", e) # type: ignore