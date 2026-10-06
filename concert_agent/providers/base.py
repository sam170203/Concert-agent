from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class CatalogTrack:
    external_id: str
    title: str
    url: str
    popularity: int | None = None


class MessagingProvider(Protocol):
    def send_text(self, to: str, body: str) -> str | None: ...


class MusicProvider(Protocol):
    def discover(self, artist: str, limit: int) -> list[CatalogTrack]: ...
