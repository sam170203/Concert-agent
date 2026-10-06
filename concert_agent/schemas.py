from datetime import date, time

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    artist: str = Field(min_length=1, max_length=200)
    concert_date: date
    send_time: time = time(20, 0)
    timezone: str = "UTC"


class ParticipantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=40)


class TrackCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str
    external_id: str | None = None
    provider: str = "manual"
    popularity: int | None = None
