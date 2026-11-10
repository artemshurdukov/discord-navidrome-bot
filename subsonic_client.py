import hashlib
import aiohttp
import secrets
import string
import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class SubsonicClient:
    def __init__(self, base_url: str, username: str, password: str, session: aiohttp.ClientSession):
        # Base URL should point to the /rest/ directory
        self.base_url = f"{base_url.rstrip('/')}/rest"
        self.username = username
        self.password = password
        self.session = session
        # Salt should be a random string (alphanumeric)
        self.salt = secrets.token_urlsafe(16)

    def _get_auth_params(self) -> Dict[str, str]:
        # Compute token = md5(password + salt)
        combined = (self.password + self.salt).encode('utf-8')
        token = hashlib.md5(combined).hexdigest()
        
        return {
            "u": self.username,
            "t": token,
            "s": self.salt,
            "v": "1.16.1",
            "c": "DiscordBot",
            "f": "json"
        }

    async def _request(self, endpoint: str, params: Dict[str, str] = None) -> Optional[Dict]:
        url = f"{self.base_url}/{endpoint}"
        auth_params = self._get_auth_params()
        if params:
            auth_params.update(params)
            
        try:
            async with self.session.get(url, params=auth_params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Request failed: {url} - Status: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error during request to {url}: {e}")
            return None

    async def search_track(self, query: str) -> List[Dict]:
        # search3 endpoint with .view suffix
        data = await self._request("search3.view", {"query": query})
        if data and "subsonic-response" in data:
            response = data["subsonic-response"]
            if "searchResult3" in response:
                return response["searchResult3"].get("song", [])
        return []

    async def get_stream_url(self, track_id: str) -> Optional[str]:
        # Just construct the URL for the stream.
        # Query parameters: id, u, t, s, v, c, format, maxBitRate
        params = {
            "id": track_id,
            "u": self.username,
            "t": self._get_auth_params()["t"],
            "s": self.salt,
            "v": "1.16.1",
            "c": "DiscordBot",
            "format": "mp3",
            "maxBitRate": "192"
        }
        
        # Construct the URL using urlencode to ensure characters are correctly escaped
        # We use the base_url which already includes /rest
        from urllib.parse import urlencode
        query_string = urlencode(params)
        return f"{self.base_url}/stream.view?{query_string}"
