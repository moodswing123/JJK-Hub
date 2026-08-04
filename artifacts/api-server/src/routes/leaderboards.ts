import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query } from "../lib/db";

const router: IRouter = Router();

function formatEntry(row: Record<string, unknown>, idx: number) {
  const wins = Number(row.wins ?? 0);
  const losses = Number(row.losses ?? 0);
  const total = wins + losses;
  return {
    rank_position: idx + 1,
    user_id: Number(row.user_id),
    display_name: String(row.display_name),
    username: row.username as string | null,
    character_id: row.character_id ? Number(row.character_id) : null,
    level: Number(row.level),
    rank: String(row.rank),
    yen: Number(row.yen),
    wins,
    losses,
    win_rate: total > 0 ? Math.round((wins / total) * 1000) / 10 : 0,
    avatar_url: row.avatar_url as string | null,
  };
}

router.get("/leaderboards/level", requireAuth, async (req, res): Promise<void> => {
  const limit = Math.min(50, Number(req.query.limit ?? 20));
  const rows = await query<Record<string, unknown>>(
    "SELECT p.*, dp.avatar_url FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id ORDER BY p.level DESC, p.xp DESC LIMIT $1",
    [limit]
  );
  res.json(rows.map(formatEntry));
});

router.get("/leaderboards/wealth", requireAuth, async (req, res): Promise<void> => {
  const limit = Math.min(50, Number(req.query.limit ?? 20));
  const rows = await query<Record<string, unknown>>(
    "SELECT p.*, dp.avatar_url FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id ORDER BY p.yen DESC LIMIT $1",
    [limit]
  );
  res.json(rows.map(formatEntry));
});

router.get("/leaderboards/pvp", requireAuth, async (req, res): Promise<void> => {
  const limit = Math.min(50, Number(req.query.limit ?? 20));
  const rows = await query<Record<string, unknown>>(
    "SELECT p.*, dp.avatar_url FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id ORDER BY p.wins DESC LIMIT $1",
    [limit]
  );
  res.json(rows.map(formatEntry));
});

export default router;
