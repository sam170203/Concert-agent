# Concert Agent 🎤

Turn the days before a concert into a shared listening ritual.

Concert Agent sends friends one artist track each day before a concert, collects 1–10 ratings from replies, avoids repeats, and produces a group recap before showtime.

> First real campaign: Nanku — 16 October 2026.

## MVP

- FastAPI API + webhook receiver
- Provider-based architecture: messaging and music are replaceable adapters
- WhatsApp Cloud API adapter
- Spotify catalog adapter (optional; manual tracks work without Spotify)
- SQLite locally; PostgreSQL via `DATABASE_URL` in production
- Campaign engine chooses an unsent track and sends it to every active participant
- Rating parser understands `8`, `8/10`, `8.5`, `solid 9`, etc.
- Cron-friendly dispatch endpoint; no always-on in-process scheduler required
- Concert recap endpoint

## Quick start

```bash
git clone https://github.com/sam170203/Concert-agent.git
cd Concert-agent
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn concert_agent.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Flow

1. Create a campaign with artist, concert date, timezone and daily send time.
2. Add opted-in friends.
3. Add tracks manually or discover public catalog tracks through Spotify.
4. Call `/api/dispatch/due` from cron. The engine sends at most one track per campaign per local day.
5. Friends reply with ratings such as `8`, `8/10`, or `solid 9`.
6. The WhatsApp webhook parses and stores the rating against that friend's latest drop.
7. `/api/campaigns/{id}/recap` produces group stats.

## WhatsApp setup

Copy `.env.example` to `.env` and configure the WhatsApp Cloud API credentials. Point the Meta webhook callback at:

```text
https://YOUR_DOMAIN/webhooks/whatsapp
```

Keep `DRY_RUN=true` while developing. Production-initiated WhatsApp conversations must follow Meta's current opt-in, template, and messaging-window requirements.

## Scheduling

Run this from your hosting provider's cron every few minutes:

```text
POST /api/dispatch/due
```

Protect it with `X-Cron-Secret` in production. The endpoint checks each campaign's timezone and send time itself.

## Architecture

```text
Campaign + participants
        │
        v
 CampaignEngine ─────> MusicProvider
        │                 └─ Spotify / manual
        v
 MessagingProvider
        └─ WhatsApp Cloud API
        │
        v
     Friends
        │ replies "8.5/10"
        v
 WhatsApp webhook
        │
        v
 Rating parser ─────> Rating
```

Core business logic does not know about WhatsApp or Spotify. Future adapters can add Telegram, Discord, YouTube Music, or another catalog without rewriting campaign logic.

## API

- `GET /health`
- `POST /api/campaigns`
- `GET /api/campaigns/{id}`
- `POST /api/campaigns/{id}/participants`
- `POST /api/campaigns/{id}/tracks`
- `POST /api/campaigns/{id}/tracks/discover`
- `GET /api/campaigns/{id}/next`
- `POST /api/campaigns/{id}/dispatch`
- `GET /api/campaigns/{id}/recap`
- `POST /api/dispatch/due`
- `GET|POST /webhooks/whatsapp`

## Development

```bash
pytest
ruff check .
```

## Roadmap

- CLI: `concert-agent init`
- WhatsApp template onboarding helpers
- Telegram / Discord adapters
- setlist-aware track strategy
- small campaign dashboard
- richer concert-day recap

## Security

Never commit access tokens, API secrets, phone numbers, or `.env`. Webhook signature validation is required before a serious production deployment.

## License

MIT
