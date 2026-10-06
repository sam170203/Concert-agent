import base64

import httpx

from concert_agent.config import Settings
from concert_agent.providers.base import CatalogTrack


class SpotifyProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _token(self) -> str:
        if not self.settings.spotify_client_id or not self.settings.spotify_client_secret:
            raise RuntimeError("Spotify credentials are not configured")
        raw = f"{self.settings.spotify_client_id}:{self.settings.spotify_client_secret}".encode()
        auth = base64.b64encode(raw).decode()
        response = httpx.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def discover(self, artist: str, limit: int = 10) -> list[CatalogTrack]:
        token = self._token()
        response = httpx.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": f'artist:"{artist}"', "type": "track", "limit": min(limit, 50)},
            timeout=20,
        )
        response.raise_for_status()
        items = response.json().get("tracks", {}).get("items", [])
        tracks = []
        for item in items:
            artist_names = {a["name"].casefold() for a in item.get("artists", [])}
            if artist.casefold() not in artist_names:
                continue
            tracks.append(
                CatalogTrack(
                    external_id=item["id"],
                    title=item["name"],
                    url=item["external_urls"]["spotify"],
                    popularity=item.get("popularity"),
                )
            )
        return sorted(tracks, key=lambda t: t.popularity or 0, reverse=True)
