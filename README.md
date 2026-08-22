# Cursed Realm — JJK RPG Dashboard

A professional, responsive player command center for the JJK Telegram RPG. The frontend authenticates players through the Telegram Login Widget, then loads the player profile and dashboard summary from the existing API contract.

## Vercel deployment

Use the repository root as the Vercel Root Directory. Use `pnpm build` as the Build Command and `dist/public` as the Output Directory. Set `VITE_TELEGRAM_BOT_USERNAME` to `jjk_rpg_bot` without the `@` symbol. Leave `VITE_API_BASE_URL` empty when the API is served at the same origin under `/api`; otherwise set it to the API origin ending in `/api`.

The frontend never stores bot tokens, database credentials, or owner IDs. Those belong only in the API deployment environment.
