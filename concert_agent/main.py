import hashlib
import hmac
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from concert_agent.config import get_settings
from concert_agent.database import Base, engine, get_db
from concert_agent.engine import choose_track, dispatch_campaign
from concert_agent.models import Campaign, Delivery, Participant, Rating, Track
from concert_agent.providers.spotify import SpotifyProvider
from concert_agent.providers.whatsapp import WhatsAppProvider
from concert_agent.rating_parser import parse_rating
from concert_agent.schemas import CampaignCreate, ParticipantCreate, TrackCreate

settings = get_settings()
app = FastAPI(title="Concert Agent", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"status": "ok", "dry_run": settings.dry_run}


@app.post("/api/campaigns")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(400, "Unknown timezone") from exc
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return {"id": campaign.id, "artist": campaign.artist, "concert_date": campaign.concert_date}


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return {
        "id": campaign.id,
        "artist": campaign.artist,
        "concert_date": campaign.concert_date,
        "send_time": campaign.send_time,
        "timezone": campaign.timezone,
        "participants": len(campaign.participants),
        "tracks": len(campaign.tracks),
    }


@app.post("/api/campaigns/{campaign_id}/participants")
def add_participant(campaign_id: int, payload: ParticipantCreate, db: Session = Depends(get_db)):
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, "Campaign not found")
    participant = Participant(campaign_id=campaign_id, **payload.model_dump())
    db.add(participant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Participant already exists") from exc
    db.refresh(participant)
    return {"id": participant.id, "name": participant.name}


@app.post("/api/campaigns/{campaign_id}/tracks")
def add_track(campaign_id: int, payload: TrackCreate, db: Session = Depends(get_db)):
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, "Campaign not found")
    data = payload.model_dump()
    data["external_id"] = data["external_id"] or hashlib.sha256(payload.url.encode()).hexdigest()[:32]
    track = Track(campaign_id=campaign_id, **data)
    db.add(track)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Track already exists") from exc
    db.refresh(track)
    return {"id": track.id, "title": track.title}


@app.post("/api/campaigns/{campaign_id}/tracks/discover")
def discover_tracks(campaign_id: int, limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    discovered = SpotifyProvider(settings).discover(campaign.artist, limit)
    added = 0
    for item in discovered:
        exists = db.scalar(
            select(Track).where(Track.campaign_id == campaign_id, Track.external_id == item.external_id)
        )
        if exists:
            continue
        db.add(
            Track(
                campaign_id=campaign_id,
                title=item.title,
                url=item.url,
                external_id=item.external_id,
                provider="spotify",
                popularity=item.popularity,
            )
        )
        added += 1
    db.commit()
    return {"discovered": len(discovered), "added": added}


@app.get("/api/campaigns/{campaign_id}/next")
def next_track(campaign_id: int, db: Session = Depends(get_db)):
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, "Campaign not found")
    track = choose_track(db, campaign_id)
    return None if not track else {"id": track.id, "title": track.title, "url": track.url}


@app.post("/api/campaigns/{campaign_id}/dispatch")
def dispatch(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    local_now = datetime.now(ZoneInfo(campaign.timezone))
    return dispatch_campaign(db, campaign, WhatsAppProvider(settings), local_now.date())


@app.post("/api/dispatch/due")
def dispatch_due(
    x_cron_secret: str | None = Header(None), db: Session = Depends(get_db)
):
    if settings.app_env == "production" and not hmac.compare_digest(
        x_cron_secret or "", settings.cron_secret
    ):
        raise HTTPException(401, "Invalid cron secret")
    results = []
    for campaign in db.scalars(select(Campaign).where(Campaign.active.is_(True))).all():
        now = datetime.now(ZoneInfo(campaign.timezone))
        if now.date() >= campaign.concert_date:
            continue
        scheduled = now.replace(
            hour=campaign.send_time.hour,
            minute=campaign.send_time.minute,
            second=0,
            microsecond=0,
        )
        if 0 <= (now - scheduled).total_seconds() < 600:
            result = dispatch_campaign(db, campaign, WhatsAppProvider(settings), now.date())
            results.append({"campaign_id": campaign.id, **result})
    return {"results": results}


@app.get("/api/campaigns/{campaign_id}/recap")
def recap(campaign_id: int, db: Session = Depends(get_db)):
    if not db.get(Campaign, campaign_id):
        raise HTTPException(404, "Campaign not found")
    rows = db.execute(
        select(Track.title, func.avg(Rating.value), func.count(Rating.id))
        .join(Delivery, Delivery.track_id == Track.id)
        .join(Rating, Rating.delivery_id == Delivery.id)
        .where(Track.campaign_id == campaign_id)
        .group_by(Track.id)
        .order_by(func.avg(Rating.value).desc())
    ).all()
    return {
        "tracks": [
            {"title": title, "average": round(float(avg), 2), "ratings": count}
            for title, avg, count in rows
        ]
    }


@app.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hmac.compare_digest(
        hub_verify_token or "", settings.whatsapp_verify_token
    ):
        return hub_challenge or ""
    raise HTTPException(403, "Webhook verification failed")


def _verify_signature(raw: bytes, signature: str | None) -> None:
    if not settings.whatsapp_app_secret:
        if settings.app_env == "production":
            raise HTTPException(500, "WHATSAPP_APP_SECRET is required in production")
        return
    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode(), raw, hashlib.sha256
    ).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid webhook signature")


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    _verify_signature(raw, x_hub_signature_256)
    payload = await request.json()
    stored = 0
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                if message.get("type") != "text":
                    continue
                phone = message.get("from", "")
                text = message.get("text", {}).get("body", "")
                value = parse_rating(text)
                if value is None:
                    continue
                participant = db.scalar(
                    select(Participant)
                    .where(Participant.phone == phone, Participant.active.is_(True))
                    .order_by(Participant.id.desc())
                )
                if not participant:
                    continue
                delivery = db.scalar(
                    select(Delivery)
                    .where(Delivery.participant_id == participant.id)
                    .order_by(Delivery.sent_at.desc())
                )
                if not delivery:
                    continue
                rating = db.scalar(select(Rating).where(Rating.delivery_id == delivery.id))
                if rating:
                    rating.value, rating.raw_text = value, text
                else:
                    db.add(Rating(delivery_id=delivery.id, value=value, raw_text=text))
                stored += 1
    db.commit()
    return {"received": True, "ratings_stored": stored}
