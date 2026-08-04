---
name: JJK Dashboard Architecture
description: Two-artifact setup for the JJK RPG dashboard — API server and web frontend routing.
---

## Architecture

- **api-server** (`kind: api`, port 8080): serves Express routes under `/api/*`
- **jjk-dashboard** (`kind: web`, port 24438): React+Vite frontend at path `/`

## Routing

Replit's path-based proxy handles routing:
- `/api/*` → port 8080 (api-server)
- `/*` → port 24438 (jjk-dashboard)

**No Vite proxy is needed.** Browser fetches to `/api/...` route through Replit's proxy directly to the API server. 

## Database

- Bot's existing Neon DB: accessed via `POSTGRES_URL` secret
- New dashboard tables created at startup: `dashboard_profiles`, `transactions`, `notifications`, `announcements`, `casino_sessions`, `marketplace_listings`, `audit_logs`
- Raw SQL via `pg` Pool — no Drizzle ORM for these tables (bot uses raw SQL)

**Why:** The bot's tables are raw SQL from Python; consistency matters. The lib/db package uses DATABASE_URL (Replit's built-in DB) — do NOT change it.

## API Server

- `artifacts/api-server/src/lib/db.ts` — pg Pool using `POSTGRES_URL`
- `artifacts/api-server/src/lib/auth.ts` — JWT sign/verify, `requireAuth` middleware
- `artifacts/api-server/src/lib/telegram.ts` — Telegram hash verification
- All routes under `artifacts/api-server/src/routes/`

## Key Env Vars

- `POSTGRES_URL` — Neon connection string (secret)
- `TELEGRAM_BOT_TOKEN` — for Telegram auth verification (secret)
- `JWT_SECRET` — for JWT tokens (env var)
- `OWNER_ID` — admin Telegram user ID (env var, `8965170897`)
- `SESSION_SECRET` — exists but unused currently
