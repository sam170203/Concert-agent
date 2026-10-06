from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from concert_agent.models import Campaign, Delivery, Participant, Track
from concert_agent.providers.base import MessagingProvider


def build_message(campaign: Campaign, track: Track, day_number: int) -> str:
    days_left = max((campaign.concert_date - date.today()).days, 0)
    return (
        f"🎧 CONCERT AGENT · Day {day_number}\n\n"
        f"Today's {campaign.artist} track:\n🎵 {track.title}\n{track.url}\n\n"
        f"{days_left} day{'s' if days_left != 1 else ''} to the concert. "
        "Listen properly 😭\n\nReply with your rating /10."
    )


def choose_track(db: Session, campaign_id: int) -> Track | None:
    used_ids = select(Delivery.track_id).where(Delivery.campaign_id == campaign_id)
    return db.scalar(
        select(Track)
        .where(Track.campaign_id == campaign_id, Track.id.not_in(used_ids))
        .order_by(Track.popularity.desc().nullslast(), Track.id)
        .limit(1)
    )


def dispatch_campaign(
    db: Session,
    campaign: Campaign,
    provider: MessagingProvider,
    local_date: date,
) -> dict:
    existing = db.scalar(
        select(func.count(Delivery.id)).where(
            Delivery.campaign_id == campaign.id, Delivery.local_date == local_date
        )
    )
    if existing:
        return {"status": "already_dispatched", "sent": 0}

    track = choose_track(db, campaign.id)
    if not track:
        return {"status": "no_tracks", "sent": 0}

    day_number = (
        db.scalar(select(func.count(func.distinct(Delivery.local_date))).where(Delivery.campaign_id == campaign.id))
        or 0
    ) + 1
    participants = db.scalars(
        select(Participant).where(
            Participant.campaign_id == campaign.id, Participant.active.is_(True)
        )
    ).all()

    sent = 0
    for participant in participants:
        message_id = provider.send_text(participant.phone, build_message(campaign, track, day_number))
        db.add(
            Delivery(
                campaign_id=campaign.id,
                participant_id=participant.id,
                track_id=track.id,
                local_date=local_date,
                provider_message_id=message_id,
            )
        )
        sent += 1
    db.commit()
    return {"status": "sent", "sent": sent, "track": track.title, "day": day_number}
