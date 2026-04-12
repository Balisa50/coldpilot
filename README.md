# ColdPilot

Autonomous cold outreach agent with two modes:

- **Hunter** — Business outreach: finds decision-makers at target companies, researches them, writes personalised emails, sends & follows up
- **Seeker** — Job hunting: targets hiring managers at companies you want to work at, crafts tailored cold emails from your CV

## Architecture

```
coldpilot/
  backend/           Python FastAPI
    pipeline/        contact_finder -> researcher -> email_writer -> sender -> followup
    services/        hunter.io, tavily, groq, smtp
    scheduler/       APScheduler (follow-ups, approved email dispatch, daily limits)
    routers/         REST API + SSE streaming
  dashboard/         Next.js 16 + Tailwind v4
```

**Database**: SQLite (campaigns, prospects, emails, followup_schedule, action_log, daily_send_log)

**APIs**: Hunter.io (contacts), Tavily (research), Groq LLaMA 3.3 70B (email writing), Gmail SMTP (sending)

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example ../.env   # fill in your API keys
uvicorn main:app --reload
```

The server runs at `http://localhost:8000`. First run creates the SQLite database automatically.

### 2. Dashboard

```bash
cd dashboard
npm install
npm run dev
```

Opens at `http://localhost:3000`.

## Autonomy Levels

| Level | Behaviour |
|-------|-----------|
| **Copilot** | Pipeline stops at email draft — you approve each email before it sends |
| **Supervised** | Auto-approves but streams live progress via SSE so you can watch & pause |
| **Full Auto** | Runs the entire pipeline autonomously |

## Email Safety

- **Warm-up schedule**: 5 → 10 → 20 → 35 → 50 emails/day over 3 weeks
- **Random spacing**: 45-120 seconds between sends
- **Dry run mode**: Full pipeline without actually sending (default for new campaigns)
- **Bounce detection**: Permanent failures (5xx) auto-mark prospects as bounced

## API Endpoints

32 endpoints across 5 routers:

- `GET/POST /api/campaigns` — CRUD + start/pause/stream
- `GET/POST /api/campaigns/{id}/prospects` — Prospect management
- `GET /api/emails/pending` — Approval queue
- `POST /api/emails/{id}/approve|reject|rewrite` — Email actions
- `GET /api/activity` — Action log
- `GET /api/stats` — Dashboard aggregates
- `GET /api/settings` — Service configuration status
- `GET /api/health` — Health check

## Environment Variables

See `.env.example` for the full list. You need:

- **HUNTER_API_KEY** — Free tier: 25 searches/month
- **TAVILY_API_KEY** — Free tier: 1000 searches/month
- **GROQ_API_KEY** — Free tier with generous limits
- **SMTP credentials** — Gmail app password recommended

## License

MIT
