import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";
import { buildPlayer } from "./auth";

const router: IRouter = Router();

router.get("/players/me", requireAuth, async (req, res): Promise<void> => {
  const player = await buildPlayer(req.user!.userId);
  if (!player) { res.status(404).json({ error: "Player not found" }); return; }
  res.json(player);
});

router.get("/players/me/dashboard", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const [player, announcements, topPlayers, recentActivity] = await Promise.all([
    buildPlayer(userId),
    query("SELECT * FROM announcements ORDER BY pinned DESC, created_at DESC LIMIT 5"),
    query(
      "SELECT p.user_id, p.display_name, p.username, p.level, p.rank, p.yen, p.wins, p.losses, dp.avatar_url FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id ORDER BY p.level DESC, p.yen DESC LIMIT 5"
    ),
    query(
      "SELECT id, type, message, created_at FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 10",
      [userId]
    ),
  ]);

  if (!player) { res.status(404).json({ error: "Not found" }); return; }

  const totalPlayers = await queryOne<{count: string}>("SELECT COUNT(*) as count FROM players");
  const onlineCount = Math.max(1, Math.floor(Number(totalPlayers?.count ?? 1) * 0.05));

  const now = new Date();
  const lastDaily = player.last_daily ? new Date(player.last_daily) : null;
  const canClaim = !lastDaily || (now.getTime() - lastDaily.getTime()) > 24 * 60 * 60 * 1000;
  const nextClaimAt = lastDaily ? new Date(lastDaily.getTime() + 24 * 60 * 60 * 1000).toISOString() : null;

  const formattedTop = topPlayers.map((p, i) => {
    const wins = Number(p.wins ?? 0);
    const losses = Number(p.losses ?? 0);
    const total = wins + losses;
    return {
      rank_position: i + 1,
      user_id: Number(p.user_id),
      display_name: String(p.display_name),
      username: p.username as string | null,
      character_id: null,
      level: Number(p.level),
      rank: String(p.rank),
      yen: Number(p.yen),
      wins,
      losses,
      win_rate: total > 0 ? Math.round((wins / total) * 1000) / 10 : 0,
      avatar_url: p.avatar_url as string | null,
    };
  });

  res.json({
    player,
    online_count: onlineCount,
    recent_activity: recentActivity.map(r => ({
      id: Number(r.id),
      type: String(r.type),
      message: String(r.message),
      created_at: String(r.created_at),
    })),
    announcements: announcements.map(a => ({
      id: Number(a.id),
      title: String(a.title),
      content: String(a.content),
      author_id: null,
      author_name: null,
      pinned: a.pinned === true,
      created_at: String(a.created_at),
    })),
    daily_status: {
      can_claim: canClaim,
      next_claim_at: nextClaimAt,
      streak: 1,
      last_claimed_at: player.last_daily,
    },
    top_players: formattedTop,
  });
});

router.patch("/players/me/profile", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { avatar_url, banner_url, bio, equipped_title, equipped_badge, equipped_frame, theme } = req.body;

  await query(
    `INSERT INTO dashboard_profiles (user_id, avatar_url, banner_url, bio, equipped_title, equipped_badge, equipped_frame, theme)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
     ON CONFLICT (user_id) DO UPDATE SET
       avatar_url=COALESCE($2, dashboard_profiles.avatar_url),
       banner_url=COALESCE($3, dashboard_profiles.banner_url),
       bio=COALESCE($4, dashboard_profiles.bio),
       equipped_title=COALESCE($5, dashboard_profiles.equipped_title),
       equipped_badge=COALESCE($6, dashboard_profiles.equipped_badge),
       equipped_frame=COALESCE($7, dashboard_profiles.equipped_frame),
       theme=COALESCE($8, dashboard_profiles.theme),
       updated_at=NOW()`,
    [userId, avatar_url ?? null, banner_url ?? null, bio ?? null, equipped_title ?? null, equipped_badge ?? null, equipped_frame ?? null, theme ?? null]
  );

  const player = await buildPlayer(userId);
  res.json(player);
});

router.get("/players/:userId", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params.userId) ? req.params.userId[0] : req.params.userId;
  const userId = parseInt(raw, 10);
  if (isNaN(userId)) { res.status(400).json({ error: "Invalid userId" }); return; }

  const row = await queryOne<Record<string, unknown>>(
    "SELECT p.user_id, p.display_name, p.username, p.character_id, p.level, p.rank, p.wins, p.losses, dp.avatar_url, dp.equipped_title FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id WHERE p.user_id=$1",
    [userId]
  );
  if (!row) { res.status(404).json({ error: "Player not found" }); return; }

  const wins = Number(row.wins ?? 0);
  const losses = Number(row.losses ?? 0);
  const total = wins + losses;

  res.json({
    user_id: Number(row.user_id),
    display_name: String(row.display_name),
    username: row.username as string | null,
    character_id: row.character_id ? Number(row.character_id) : null,
    level: Number(row.level),
    rank: String(row.rank),
    wins,
    losses,
    win_rate: total > 0 ? Math.round((wins / total) * 1000) / 10 : 0,
    avatar_url: row.avatar_url as string | null,
    equipped_title: row.equipped_title as string | null,
  });
});

router.post("/players/me/character", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { character_id } = req.body;
  if (!character_id) { res.status(400).json({ error: "character_id required" }); return; }

  const char = await queryOne<Record<string, unknown>>("SELECT * FROM characters WHERE id=$1", [character_id]);
  if (!char) { res.status(404).json({ error: "Character not found" }); return; }

  const player = await buildPlayer(userId);
  if (!player) { res.status(404).json({ error: "Player not found" }); return; }

  const cost = Number(char.cost ?? 0);
  if (cost > 0 && player.yen < cost) {
    res.status(400).json({ error: `Insufficient Yen. Need ${cost}, have ${player.yen}` });
    return;
  }

  if (cost > 0) {
    await query("UPDATE players SET yen=yen-$1 WHERE user_id=$2", [cost, userId]);
  }

  await query(
    "UPDATE players SET character_id=$1,attack=$2,defense=$3,speed=$4,max_hp=$5,hp=$5,max_cursed_energy=$6,cursed_energy=$6 WHERE user_id=$7",
    [character_id, char.attack, char.defense, char.speed, char.max_hp, char.max_ce, userId]
  );

  const updated = await buildPlayer(userId);
  res.json(updated);
});

export default router;
