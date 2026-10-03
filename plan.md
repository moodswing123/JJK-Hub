# JJK RPG Dashboard Redesign

## Product direction

Replace the one-page command deck with a multi-route player portal: Overview, Market, Arcade, Treasury, Inventory, and owner-only Admin. The visual direction is **Neo-Occult Sportsbook**: a premium dark command center with electric cyan systems, ember coral actions, and warm gold yen, balancing the JJK fantasy with a modern game platform.

### Design system
- **Movement:** neo-occult control room meets editorial sports terminal.
- **Principles:** strong hierarchy, one primary task per screen, live status signals, generous whitespace, and deliberate motion only where it explains state.
- **Color philosophy:** ink navy for trust and depth; cyan for live systems; coral for battle/action; gold for yen and rewards; violet for cursed/rare content.
- **Layout:** persistent left rail on desktop, compact bottom navigation on mobile, page-specific hero header, and asymmetric content zones rather than a single scrolling wall of cards.
- **Signature elements:** vertical cursed-energy rail, segmented status pills, and sharp “match card” panels for games and trades.
- **Interaction:** every action has a visible state, server-confirmed result, cooldown or settlement feedback, and keyboard/focus support.
- **Animation:** short 160–320ms transitions, number emphasis on balance changes, no decorative motion during loading, and reduced-motion support.
- **Typography:** Space Grotesk for display, DM Sans for UI, IBM Plex Mono for balances and market data.
- **Brand essence:** “The player-owned command center for a living JJK economy.” Personality: tactical, premium, energetic.
- **Voice:** concise and cinematic: “Make your next move count.” / “Settlement confirmed. Your yen is live.”
- **Wordmark:** JJK monogram with an offset cyan vertical slash and ember dot.
- **Signature color:** electric cyan `#55d8e5`.

## Structure
- `client/src/App.tsx`: auth gate, route selection, shell, navigation, and shared balance refresh.
- `client/src/pages/Overview.tsx`: focused player snapshot and quick actions.
- `client/src/pages/MarketPage.tsx`: full-width market/trade experience.
- `client/src/pages/ArcadePage.tsx`: football, basketball, pool, and curse games with playable controls.
- `client/src/pages/TreasuryPage.tsx`: OPay instructions and receipt submission.
- `client/src/pages/AdminPage.tsx`: owner-only player/top-up/economy controls, protected server-side.
- `bot/database.py`: persistent game runs, market ticks, top-ups, and admin mutations.
- `bot/web_api.py`: authenticated player routes and server-side admin authorization.

## Behavior
- Football, basketball, and pool are deterministic skill mini-games with player input (shot direction/power/aim), server-side validation, cooldowns, and yen rewards. They never touch real money.
- Admin routes require `OWNER_ID` or `ADMIN_IDS` membership; the client flag is cosmetic only.
- Treasury receipts are queued and forwarded to the owner when Telegram credentials exist. Yen remains pending until manually verified.
- Market assets remain fictional and only affect in-game yen/holdings.
