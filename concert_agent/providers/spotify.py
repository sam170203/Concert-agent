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
        """Discover public catalog tracks, paginating Spotify's current max-10 search API."""
        token = self._token()
        wanted = max(1, min(limit, 50))
        tracks: dict[str, CatalogTrack] = {}
        offset = 0

        while len(tracks) < wanted and offset <= 1000:
            page_size = min(10, wanted - len(tracks))
            response = httpx.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "q": f'artist:"{artist}"',
                    "type": "track",
                    "market": "IN",
                    "limit": page_size,
                    "offset": offset,
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json().get("tracks", {})
            items = payload.get("items", [])
            if not items:
                break

            for item in items:
                artist_names = {a["name"].casefold() for a in item.get("artists", [])}
                if artist.casefold() not in artist_names:
                    continue
                tracks[item["id"]] = CatalogTrack(
                    external_id=item["id"],
                    title=item["name"],
                    url=item["external_urls"]["spotify"],
                    popularity=item.get("popularity"),
                )
            offset += len(items)
            if not payload.get("next"):
                break

        return sorted(tracks.values(), key=lambda t: t.popularity or 0, reverse=True)[:wanted]
