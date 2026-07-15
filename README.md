# CartIQ 🛒

A quick-commerce **cart comparator** for Indian platforms (Blinkit, Zepto, Swiggy Instamart). Build a cart once, see the total cost across every platform side by side — no more opening three apps.

CartIQ is driven by a **natural-language chat interface**: you type what you want, a Gemini agent calls the right tools (search, compare, find alternatives, wishlist), and replies with a clean comparison.

## Architecture
<img width="1440" height="2260" alt="image" src="https://github.com/user-attachments/assets/b27e3ef1-52ca-47b5-9e17-2be4f828f5b4" />


## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind |
| Backend | FastAPI, Pydantic, SQLAlchemy 2 (async), asyncpg |
| Database | PostgreSQL |
| Cache | Redis (Upstash) — 30-min search cache |
| AI | Gemini Flash + MCP server wrapping the REST tools |
| Data source | QuickCommerce API |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Deploy | Vercel (web) + Render (api) + Upstash (redis) |

## Features

- **Natural-language interface** — ask in plain English; a Gemini agent picks the right tools and replies with a clean comparison.
- **Cart comparison** — price a whole basket across every app and get the cheapest platform, with a per-item breakdown.
- **Shared virtual cart** — you *and* the AI manage the same cart; each item is tagged with the app it's recommended from.
- **Wishlist** — save products you buy often for quick recall (no prices stored until you search).
- **Fake-discount detection** — flags "discounts" where the offer price equals the MRP.
- **Location-aware pricing** — your pincode is geocoded to coordinates so results reflect your area.
- **Smart matching** — size/quantity-aware product matching with brand synonyms (so "coke" finds "Coca-Cola" and "milk 1L" doesn't match a 200 ml pack).
- **Alternatives** — a brand-stripped fallback search when an item isn't available.

## Engineering highlights

- **Async end-to-end** (FastAPI · asyncpg · httpx). The workload is I/O-bound, so per-item cart searches fan out **concurrently** with `asyncio.gather`.
- **Layered architecture** — the frontend only ever talks to *our* API; the QuickCommerce and Gemini keys never leave the server.
- **Agent over MCP** — the same tools that power the Gemini agent are exposed as an **MCP server**, so any MCP client can drive CartIQ.
- **Redis caching** — search results are cached (30-min TTL, keyed by query + location) to avoid re-spending API credits.
- **Resilient by design** — bounded timeouts, retry caps, and graceful error surfacing; failures degrade to a clear message instead of hanging.
- **Mock ↔ live toggle** — runs on realistic mock data by default; one env flag (`USE_MOCK_QC`) switches to the live API.

## Getting started

Prerequisites: **Docker**, **Python 3.12**, **Node 20+**.

```bash
# 1. Infrastructure — Postgres + Redis
cd services/api
docker compose up -d

# 2. Backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in the values
alembic upgrade head             # create the tables
uvicorn main:app --reload        # http://localhost:8000  (docs at /docs)

# 3. Frontend  (in a second terminal)
cd apps/web
npm install
npm run dev                       # http://localhost:3000
```

## Project structure

```
CartIQ/
├── apps/
│   └── web/                 # Next.js frontend (chat UI, cart, wishlist)
└── services/
    └── api/                 # FastAPI backend
        ├── routers/         # HTTP routes (auth, search, compare, cart, chat …)
        ├── agent/           # Gemini agent + tools (function calling)
        ├── services/        # QC client, Redis cache, cart store, geocoding
        ├── models/          # SQLAlchemy ORM models
        ├── schemas/         # Pydantic request/response models
        └── mcp_server.py    # MCP server exposing the tools
```
