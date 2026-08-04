import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { signToken } from "../lib/auth";
import { verifyTelegramAuth } from "../lib/telegram";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

router.post("/auth/telegram", async (req, res): Promise<void> => {
  const data = req.body;
  if (!data?.id || !data?.hash) {
    res.status(400).json({ error: "Missing required fields" });
    return;
  }

  // Skip hash verification in dev mode for testing
  const isDev = process.env.NODE_ENV !== "production";
  if (!isDev) {
    const valid = verifyTelegramAuth(data);
    if (!valid) {
      res.status(401).json({ error: "Invalid Telegram authentication data" });
      return;
    }
  }

  const userId = Number(data.id);
  const username = data.username ?? null;
  const displayName = [data.first_name, data.last_name].filter(Boolean).join(" ") || username || `User${userId}`;

  // Upsert player in bot's players table
  const existing = await queryOne("SELECT user_id FROM players WHERE user_id=$1", [userId]);
  if (!existing) {
    await query(
      `INSERT INTO players (user_id,username,display_name,level,xp,xp_needed,rank,yen,hp,max_hp,cursed_energy,max_cursed_energy,attack,defense,speed,wins,losses,techniques,artifacts,inventory,created_at)
       VALUES ($1,$2,$3,1,0,100,'Grade 4',5000,100,100,50,50,10,5,10,0,0,'[]','[]','[]',$4)
       ON CONFLICT (user_id) DO UPDATE SET username=$2, display_name=$3`,
      [userId, username, displayName, new Date().toISOString()]
    );
  } else {
    await query("UPDATE players SET username=$2, display_name=$3 WHERE user_id=$1", [userId, username, displayName]);
  }

  // Upsert dashboard profile
  await query(
    `INSERT INTO dashboard_profiles (user_id, avatar_url)
     VALUES ($1, $2)
     ON CONFLICT (user_id) DO NOTHING`,
    [userId, data.photo_url ?? null]
  );

  const token = signToken({ userId, username, displayName });
  const player = await buildPlayer(userId);

  res.json({ token, player });
});

router.get("/auth/me", requireAuth, async (req, res): Promise<void> => {
  const player = await buildPlayer(req.user!.userId);
  if (!player) {
    res.status(401).json({ error: "Player not found" });
    return;
  }
  res.json(player);
});

router.post("/auth/logout", requireAuth, async (_req, res): Promise<void> => {
  res.json({ success: true, message: "Logged out successfully" });
});

export async function buildPlayer(userId: number) {
  const row = await queryOne<Record<string, unknown>>(
    "SELECT p.*, dp.avatar_url, dp.banner_url, dp.bio, dp.equipped_title, dp.equipped_badge, dp.equipped_frame, dp.theme, dp.elixirs, dp.is_admin, dp.is_banned FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id WHERE p.user_id=$1",
    [userId]
  );
  if (!row) return null;

  const wins = Number(row.wins ?? 0);
  const losses = Number(row.losses ?? 0);
  const total = wins + losses;

  const domain = await queryOne<Record<string, unknown>>(
    "SELECT * FROM user_domains WHERE user_id=$1 ORDER BY id DESC LIMIT 1",
    [userId]
  );

  let techniques: string[] = [];
  let inventory: number[] = [];
  try { techniques = JSON.parse(String(row.techniques ?? "[]")); } catch { techniques = []; }
  try { inventory = JSON.parse(String(row.inventory ?? "[]")); } catch { inventory = []; }

  const ownerId = Number(process.env.OWNER_ID ?? 0);
  const isAdmin = row.is_admin === true || userId === ownerId;

  return {
    user_id: Number(row.user_id),
    username: row.username as string | null,
    display_name: String(row.display_name ?? ""),
    character_id: row.character_id ? Number(row.character_id) : null,
    level: Number(row.level ?? 1),
    xp: Number(row.xp ?? 0),
    xp_needed: Number(row.xp_needed ?? 100),
    rank: String(row.rank ?? "Grade 4"),
    yen: Number(row.yen ?? 0),
    hp: Number(row.hp ?? 100),
    max_hp: Number(row.max_hp ?? 100),
    cursed_energy: Number(row.cursed_energy ?? 50),
    max_cursed_energy: Number(row.max_cursed_energy ?? 50),
    attack: Number(row.attack ?? 10),
    defense: Number(row.defense ?? 5),
    speed: Number(row.speed ?? 10),
    wins,
    losses,
    win_rate: total > 0 ? Math.round((wins / total) * 1000) / 10 : 0,
    techniques,
    inventory,
    last_daily: row.last_daily as string | null,
    created_at: row.created_at as string | null,
    avatar_url: row.avatar_url as string | null,
    banner_url: row.banner_url as string | null,
    bio: row.bio as string | null,
    equipped_title: row.equipped_title as string | null,
    equipped_badge: row.equipped_badge as string | null,
    equipped_frame: row.equipped_frame as string | null,
    theme: row.theme as string | null ?? "dark",
    is_banned: row.is_banned === true,
    is_admin: isAdmin,
    elixirs: Number(row.elixirs ?? 0),
    domain_name: domain?.domain_name as string | null ?? null,
    domain_power: domain ? Number(domain.domain_power) : null,
    domain_equipped: Number(domain?.equipped ?? 0) === 1,
  };
}

export default router;
