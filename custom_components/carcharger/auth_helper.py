# auth_helper.py
import logging
import aiohttp
from aiohttp import FormData
import async_timeout
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

class AuthManager:
    """Handle API authentication for the car charger component."""

    def __init__(self, hass, host, username, password, client_id, client_secret):
        """Initialize the auth manager."""
        self.hass = hass
        self._host = host
        self._username = username
        self._password = password
        self._client_id = client_id
        self._client_secret = client_secret
        self._store = Store(hass, 1, "carcharger_token")
        self._access_token = None
        self._refresh_token = None

    async def get_access_token(self):
        """Get a valid access token, refreshing if needed."""
        if not self._access_token:
            await self.load_tokens()
        return self._access_token

    async def load_tokens(self):
        """Load tokens from storage or authenticate if needed."""
        data = await self._store.async_load()
        _LOGGER.debug("Loading token data: %s", data)

        if not data:
            _LOGGER.warning("No token data found in storage")
            await self.authenticate()
            return False

        if not isinstance(data, dict):
            _LOGGER.error("Invalid token format in storage: %s", type(data))
            await self.authenticate()
            return False

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token:
            _LOGGER.warning("Access token is empty or None")
            await self.authenticate()
            return False

        self._access_token = access_token
        self._refresh_token = refresh_token
        _LOGGER.info("Successfully loaded tokens from storage")
        return True

    async def authenticate(self):
        """Authenticate with the API."""
        url = f"https://{self._host}/v3/oauth2/token"
        payload = {
            "grant_type": "password",
            "username": self._username,
            "password": self._password,
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }

        form_data = FormData()
        for key, value in payload.items():
            form_data.add_field(key, value)

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.post(url, data=form_data) as response:
                        if response.status == 200:
                            data = await response.json()
                            access_token = data.get("access_token")
                            refresh_token = data.get("refresh_token")
                            await self.save_tokens(access_token, refresh_token)
                            return True
                        else:
                            _LOGGER.error("Failed to authenticate: %s (Status: %s)",
                                          await response.text(), response.status)
                            return False
        except Exception as e:
            _LOGGER.error("Error authenticating: %s", e)
            return False

    async def refresh_access_token(self):
        """Refresh the access token."""
        if not self._refresh_token:
            return await self.authenticate()

        url = f"https://{self._host}/v3/oauth2/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
            "client_id": self._client_id,
            "client_secret": self._client_secret
        }

        form_data = FormData()
        for key, value in payload.items():
            form_data.add_field(key, value)

        try:
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.post(url, data=form_data) as response:
                        if response.status == 200:
                            data = await response.json()
                            access_token = data.get("access_token")
                            refresh_token = data.get("refresh_token")
                            await self.save_tokens(access_token, refresh_token)
                            _LOGGER.info("Successfully refreshed access token")
                            return True
                        else:
                            _LOGGER.error("Failed to refresh token: %s (Status: %s)",
                                          await response.text(), response.status)
                            return await self.authenticate()
        except Exception as e:
            _LOGGER.error("Error refreshing access token: %s", e)
            return False

    async def save_tokens(self, access_token, refresh_token):
        """Save both tokens to storage."""
        self._access_token = access_token
        self._refresh_token = refresh_token
        await self._store.async_save({
            "access_token": access_token,
            "refresh_token": refresh_token
        })
        _LOGGER.info("Saved tokens to storage")