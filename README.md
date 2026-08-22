# JJK RPG Dashboard + Bot

This repository contains the JJK RPG dashboard frontend and a synchronized copy of the Python Telegram bot integration.

## Repository layout

The `client/` directory contains the Vite dashboard. The `bot/` directory contains the Python bot, PostgreSQL access layer, `/web` credential registration flow, and `web_api.py` credential API. The dashboard must not receive bot tokens or database credentials.

## Deployment boundary

Deploy the repository root to Vercel with `pnpm build` and `dist/public` as the output directory. Vercel serves the frontend only. The current public dashboard URL is `https://jjk-hub-api-server-5qop-ten.vercel.app/`. Run the Python bot and `bot/web_api.py` on a Python-capable host with `BOT_TOKEN`, `OWNER_ID`, `POSTGRES_URL`, `WEB_AUTH_SECRET`, and `DASHBOARD_URL` configured as private environment variables. Set the dashboard’s `VITE_API_BASE_URL` to the separate public API URL ending in `/api`; do not use the dashboard URL as the API base unless the API is deployed on the same host.

## Player access flow

A player sends `/web` to the Telegram bot, chooses a unique dashboard username, enters and confirms a password, and receives `DASHBOARD_URL`. The password is stored as a salted scrypt hash. The dashboard submits credentials to `/api/auth/password`, receives a signed token, and uses that token for `/api/auth/me` and `/api/dashboard/summary`.

## Local checks

Run `pnpm install --frozen-lockfile`, `pnpm check`, and `pnpm build` for the frontend. Run `python3 -m py_compile bot/*.py` for the bot source. Start the API with `python3 bot/web_api.py` and the bot with `python3 bot/bot.py` only after configuring the required private environment variables.
