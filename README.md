# CartIQ 🛒

A quick-commerce **cart comparator** for Indian platforms (Blinkit, Zepto, Swiggy Instamart). Build a cart once, see the total cost across every platform side by side — no more opening three apps.

CartIQ is driven by a **natural-language chat interface**: you type what you want, a Gemini agent calls the right tools (search, compare, find alternatives, wishlist), and replies with a clean comparison.

## Architecture
<figure TBI>

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
