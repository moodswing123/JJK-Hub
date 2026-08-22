# JJK RPG Dashboard + Bot

This repository contains the JJK RPG dashboard frontend and a synchronized copy of the Python Telegram bot integration.

## Repository layout

The `client/` directory contains the Vite dashboard. The `bot/` directory contains the Python bot, PostgreSQL access layer, `/web` credential registration flow, and `web_api.py` credential API. The dashboard must not receive bot tokens or database credentials.

## Deployment boundary

Deploy the repository root to Vercel with `pnpm build` and `dist/public` as the output directory. The current public dashboard and same-origin API URL is `https://jjk-hub-api-server.vercel.app/`. The Vercel project must contain the private `POSTGRES_URL`, `WEB_AUTH_SECRET`, `DASHBOARD_ORIGIN`, and `OWNER_ID` variables. The Telegram bot separately requires `BOT_TOKEN`, `OWNER_ID`, `POSTGRES_URL`, `WEB_AUTH_SECRET`, and `DASHBOARD_URL`; set `DASHBOARD_URL` to the canonical Vercel URL. Because the API is deployed in the same Vercel project, the frontend uses `/api` and does not require a separate `VITE_API_BASE_URL`.

## Player access flow

A player sends `/web` to the Telegram bot, chooses a unique dashboard username, enters and confirms a password, and receives `DASHBOARD_URL`. The password is stored as a salted scrypt hash. The dashboard submits credentials to `/api/auth/password`, receives a signed token, and uses that token for `/api/auth/me` and `/api/dashboard/summary`.

## Local checks

Run `pnpm install --frozen-lockfile`, `pnpm check`, and `pnpm build` for the frontend. Run `python3 -m py_compile bot/*.py` for the bot source. Start the API with `python3 bot/web_api.py` and the bot with `python3 bot/bot.py` only after configuring the required private environment variables.
