# Deploying CartIQ

CartIQ deploys as three managed pieces:

| Piece | Host | What it is |
|---|---|---|
| **Frontend** | Vercel | Next.js chat UI |
| **Backend** | Render | FastAPI API + MCP + agent |
| **Postgres** | Render | users, wishlist, cart history |
| **Redis** | Upstash | search cache + virtual cart |

The backend reads all config from **environment variables** (see `services/api/.env.example`), so the only difference between local and prod is the values you set.

---

## 0. Push to GitHub

```bash
git add -A
git commit -m "CartIQ v1"
git push origin main
```

Render and Vercel both deploy from this repo.

---

## 1. Redis — Upstash (free)

1. Create a database at <https://upstash.com> (Redis, pick a region near your Render region).
2. Copy the **`rediss://…` connection URL** (TLS). You'll paste it as `REDIS_URL` on Render.

---

## 2. Backend + Postgres — Render (free)

**Option A — Blueprint (recommended).** The repo ships [`render.yaml`](render.yaml), which provisions the API **and** a Postgres database in one step.

1. Go to <https://dashboard.render.com> → **New → Blueprint** → connect this repo.
2. Render reads `render.yaml`, creates `cartiq-api` + `cartiq-db`, and prompts for the secret env vars (`sync: false`):
   - `QUICKCOMMERCE_API_KEY` — your QC key
   - `GEMINI_API_KEY` — your Google AI Studio key
   - `REDIS_URL` — the Upstash `rediss://…` URL from step 1
   - `CORS_ORIGINS` — leave as `http://localhost:3000` for now; update after step 3
3. `DATABASE_URL` and `JWT_SECRET_KEY` are wired/generated automatically.
4. Deploy. The start command runs `alembic upgrade head` (creates tables) then boots uvicorn.
5. Verify: open `https://cartiq-api.onrender.com/health` → `{"status":"ok","mock_qc":true}` and `/docs` for the API.

**Option B — Docker.** Point any Docker host at [`services/api/Dockerfile`](services/api/Dockerfile) and set the same env vars manually.

> **Note:** `config.py` auto-rewrites Render's `postgresql://` URL to the `postgresql+asyncpg://` form the async driver needs — no manual editing.
>
> **Free tier:** the Render service sleeps after inactivity; the first request after idle takes ~30–50s to wake.

---

## 3. Frontend — Vercel (free)

1. Go to <https://vercel.com> → **Add New → Project** → import this repo.
2. **Root Directory:** set to **`apps/web`** (this is a monorepo — important).
3. Framework preset auto-detects **Next.js**. Leave build/output defaults.
4. **Environment Variable:**
   - `NEXT_PUBLIC_API_URL` = your Render URL, e.g. `https://cartiq-api.onrender.com`
5. Deploy. You'll get a URL like `https://cartiq.vercel.app`.

---

## 4. Close the loop (CORS)

The browser will block calls until the backend allows the frontend's origin.

1. On **Render**, set `CORS_ORIGINS` = your Vercel URL (e.g. `https://cartiq.vercel.app`).
   For multiple, comma-separate them.
2. Save → Render redeploys.

Now open the Vercel URL, sign up, and chat. 🎉

---

## Going live with real prices

The app runs on **mock data** by default (`USE_MOCK_QC=true`) because the QuickCommerce trial credits are exhausted. When you buy a credit pack:

1. On Render, set `USE_MOCK_QC=false`.
2. Ensure `QUICKCOMMERCE_API_KEY` is valid with credits.
3. Redeploy. Search/compare now hit the live API — the pincode selector then makes results location-accurate.

## Production checklist

- [ ] `JWT_SECRET_KEY` is a strong random value (Render generates one)
- [ ] `.env` is **never** committed (it's gitignored)
- [ ] `CORS_ORIGINS` lists only your real frontend origin(s)
- [ ] `REDIS_URL` uses `rediss://` (TLS) in production
- [ ] `GEMINI_API_KEY` set, `GEMINI_MODEL=gemini-flash-lite-latest`
- [ ] `/health` returns 200 on the deployed API
