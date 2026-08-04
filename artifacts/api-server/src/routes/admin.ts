import { Router, type IRouter, type Request, type Response, type NextFunction } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";
import { buildPlayer } from "./auth";

const router: IRouter = Router();

async function requireAdmin(req: Request, res: Response, next: NextFunction): Promise<void> {
  const userId = req.user?.userId;
  if (!userId) { res.status(401).json({ error: "Not authenticated" }); return; }
  const ownerId = Number(process.env.OWNER_ID ?? 0);
  if (userId === ownerId) { next(); return; }
  const profile = await queryOne<{is_admin: boolean}>("SELECT is_admin FROM dashboard_profiles WHERE user_id=$1", [userId]);
  if (!profile?.is_admin) { res.status(403).json({ error: "Admin access required" }); return; }
  next();
}

router.get("/admin/users", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const limit = Math.min(200, Number(req.query.limit ?? 50));
  const offset = Number(req.query.offset ?? 0);
  const search = req.query.search as string | undefined;

  let sql = `SELECT p.*, dp.avatar_url, dp.banner_url, dp.bio, dp.equipped_title, dp.equipped_badge, dp.equipped_frame, dp.theme, dp.elixirs, dp.is_admin, dp.is_banned FROM players p LEFT JOIN dashboard_profiles dp ON p.user_id=dp.user_id`;
  const params: unknown[] = [];
  if (search) {
    sql += ` WHERE LOWER(p.display_name) LIKE $1 OR LOWER(p.username) LIKE $1`;
    params.push(`%${search.toLowerCase()}%`);
  }
  sql += ` ORDER BY p.level DESC LIMIT $${params.length + 1} OFFSET $${params.length + 2}`;
  params.push(limit, offset);

  const rows = await query<Record<string, unknown>>(sql, params);
  const countSql = search
    ? `SELECT COUNT(*) as cnt FROM players WHERE LOWER(display_name) LIKE $1 OR LOWER(username) LIKE $1`
    : "SELECT COUNT(*) as cnt FROM players";
  const countResult = await queryOne<{cnt: string}>(countSql, search ? [`%${search.toLowerCase()}%`] : []);

  const players = await Promise.all(rows.map(r => buildPlayer(Number(r.user_id))));

  res.json({ users: players.filter(Boolean), total: Number(countResult?.cnt ?? 0) });
});

router.patch("/admin/users/:userId", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const adminId = req.user!.userId;
  const raw = Array.isArray(req.params.userId) ? req.params.userId[0] : req.params.userId;
  const targetId = parseInt(raw, 10);
  const { yen, xp, level, hp, cursed_energy, is_banned, rank, elixirs } = req.body;

  const updates: string[] = [];
  const params: unknown[] = [];

  if (yen !== undefined && yen !== null) { updates.push(`yen=$${params.length + 1}`); params.push(Number(yen)); }
  if (xp !== undefined && xp !== null) { updates.push(`xp=$${params.length + 1}`); params.push(Number(xp)); }
  if (level !== undefined && level !== null) { updates.push(`level=$${params.length + 1}`); params.push(Number(level)); }
  if (hp !== undefined && hp !== null) { updates.push(`hp=$${params.length + 1}`); params.push(Number(hp)); }
  if (cursed_energy !== undefined && cursed_energy !== null) { updates.push(`cursed_energy=$${params.length + 1}`); params.push(Number(cursed_energy)); }
  if (rank !== undefined && rank !== null) { updates.push(`rank=$${params.length + 1}`); params.push(String(rank)); }

  if (updates.length > 0) {
    params.push(targetId);
    await query(`UPDATE players SET ${updates.join(",")} WHERE user_id=$${params.length}`, params);
  }

  if (is_banned !== undefined && is_banned !== null) {
    await query(
      "INSERT INTO dashboard_profiles (user_id, is_banned) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET is_banned=$2",
      [targetId, Boolean(is_banned)]
    );
  }
  if (elixirs !== undefined && elixirs !== null) {
    await query(
      "INSERT INTO dashboard_profiles (user_id, elixirs) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET elixirs=$2",
      [targetId, Number(elixirs)]
    );
  }

  await query(
    "INSERT INTO audit_logs (admin_id, target_user_id, action, data) VALUES ($1,$2,$3,$4)",
    [adminId, targetId, "update_user", JSON.stringify(req.body)]
  );

  const player = await buildPlayer(targetId);
  res.json(player);
});

router.post("/admin/grants", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const adminId = req.user!.userId;
  const { user_id, grant_type, amount, item_id, reason } = req.body;
  if (!user_id || !grant_type || amount === undefined) {
    res.status(400).json({ error: "user_id, grant_type, amount required" }); return;
  }

  const targetId = Number(user_id);
  let newBalance: number | null = null;
  let message = "";

  switch (grant_type) {
    case "yen": {
      const [r] = await query<{yen: number}>(
        "UPDATE players SET yen=yen+$1 WHERE user_id=$2 RETURNING yen",
        [amount, targetId]
      );
      newBalance = r?.yen ?? null;
      message = `Granted ¥${Number(amount).toLocaleString()} to player`;
      break;
    }
    case "xp": {
      await query("UPDATE players SET xp=xp+$1 WHERE user_id=$2", [amount, targetId]);
      message = `Granted ${amount} XP to player`;
      break;
    }
    case "elixirs": {
      await query(
        "INSERT INTO dashboard_profiles (user_id, elixirs) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET elixirs=dashboard_profiles.elixirs+$2",
        [targetId, amount]
      );
      message = `Granted ${amount} Elixirs to player`;
      break;
    }
    case "item": {
      if (!item_id) { res.status(400).json({ error: "item_id required for item grant" }); return; }
      const invRow = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [targetId]);
      let inv: number[] = [];
      try { inv = JSON.parse(invRow?.inventory ?? "[]"); } catch { inv = []; }
      for (let i = 0; i < amount; i++) inv.push(Number(item_id));
      await query("UPDATE players SET inventory=$1 WHERE user_id=$2", [JSON.stringify(inv), targetId]);
      message = `Granted ${amount}x item to player`;
      break;
    }
    default:
      res.status(400).json({ error: `Unknown grant_type: ${grant_type}` }); return;
  }

  await query(
    "INSERT INTO audit_logs (admin_id, target_user_id, action, data) VALUES ($1,$2,$3,$4)",
    [adminId, targetId, "grant", JSON.stringify({ grant_type, amount, item_id, reason })]
  );
  await query(
    "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'reward','Admin Grant',$2)",
    [targetId, message + (reason ? ` (${reason})` : "")]
  );

  res.json({ success: true, message, new_balance: newBalance });
});

router.post("/admin/announcements", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const adminId = req.user!.userId;
  const { title, content, pinned = false } = req.body;
  if (!title || !content) { res.status(400).json({ error: "title and content required" }); return; }

  const [row] = await query<Record<string, unknown>>(
    "INSERT INTO announcements (title, content, author_id, pinned) VALUES ($1,$2,$3,$4) RETURNING *",
    [title, content, adminId, Boolean(pinned)]
  );
  const author = await queryOne<{display_name: string}>("SELECT display_name FROM players WHERE user_id=$1", [adminId]);

  res.status(201).json({
    id: Number(row.id),
    title: String(row.title),
    content: String(row.content),
    author_id: adminId,
    author_name: author?.display_name ?? null,
    pinned: row.pinned === true,
    created_at: String(row.created_at),
  });
});

router.get("/admin/transactions", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const limit = Math.min(200, Number(req.query.limit ?? 50));
  const status = req.query.status as string | undefined;

  let sql = "SELECT t.*, p.display_name FROM transactions t LEFT JOIN players p ON t.user_id=p.user_id";
  const params: unknown[] = [limit];
  if (status) { sql += " WHERE t.status=$2"; params.push(status); }
  sql += " ORDER BY t.created_at DESC LIMIT $1";

  const rows = await query<Record<string, unknown>>(sql, params);
  res.json(rows.map(r => ({
    id: Number(r.id),
    user_id: Number(r.user_id),
    display_name: r.display_name as string | null ?? null,
    type: String(r.type),
    amount: Number(r.amount),
    currency: String(r.currency ?? "USD"),
    yen_amount: r.yen_amount ? Number(r.yen_amount) : null,
    elixir_amount: r.elixir_amount ? Number(r.elixir_amount) : null,
    status: String(r.status),
    provider: r.provider as string | null ?? null,
    provider_tx_id: r.provider_tx_id as string | null ?? null,
    admin_note: r.admin_note as string | null ?? null,
    created_at: String(r.created_at),
  })));
});

router.patch("/admin/transactions/:id", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const adminId = req.user!.userId;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw, 10);
  const { status, admin_note } = req.body;

  const tx = await queryOne<Record<string, unknown>>("SELECT * FROM transactions WHERE id=$1", [id]);
  if (!tx) { res.status(404).json({ error: "Transaction not found" }); return; }

  const [updated] = await query<Record<string, unknown>>(
    "UPDATE transactions SET status=COALESCE($1,status), admin_note=COALESCE($2,admin_note), updated_at=NOW() WHERE id=$3 RETURNING *",
    [status ?? null, admin_note ?? null, id]
  );

  // If completing a manual yen purchase, grant the yen
  if (status === "completed" && tx.type === "manual_yen" && tx.status !== "completed" && tx.yen_amount) {
    const yenToGrant = Number(tx.yen_amount);
    await query("UPDATE players SET yen=yen+$1 WHERE user_id=$2", [yenToGrant, tx.user_id]);
    await query(
      "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'purchase','Yen Purchase Complete',$2)",
      [tx.user_id, `Your manual purchase of ¥${yenToGrant.toLocaleString()} has been completed!`]
    );
  }

  await query(
    "INSERT INTO audit_logs (admin_id, target_user_id, action, data) VALUES ($1,$2,'update_transaction',$3)",
    [adminId, tx.user_id, JSON.stringify({ transaction_id: id, status, admin_note })]
  );

  res.json({
    id: Number(updated.id),
    user_id: Number(updated.user_id),
    display_name: null,
    type: String(updated.type),
    amount: Number(updated.amount),
    currency: String(updated.currency ?? "USD"),
    yen_amount: updated.yen_amount ? Number(updated.yen_amount) : null,
    elixir_amount: updated.elixir_amount ? Number(updated.elixir_amount) : null,
    status: String(updated.status),
    provider: updated.provider as string | null ?? null,
    provider_tx_id: updated.provider_tx_id as string | null ?? null,
    admin_note: updated.admin_note as string | null ?? null,
    created_at: String(updated.created_at),
  });
});

router.get("/admin/analytics", requireAuth, requireAdmin, async (_req, res): Promise<void> => {
  const today = new Date().toISOString().split("T")[0];

  const [totalPlayers, activePlayers, newToday, totalBattles, totalYen, topChars, rankDist] = await Promise.all([
    queryOne<{cnt: string}>("SELECT COUNT(*) as cnt FROM players"),
    queryOne<{cnt: string}>("SELECT COUNT(*) as cnt FROM players WHERE created_at >= NOW() - INTERVAL '24 hours'"),
    queryOne<{cnt: string}>(`SELECT COUNT(*) as cnt FROM players WHERE created_at >= '${today}'`),
    queryOne<{cnt: string}>("SELECT COUNT(*) as cnt FROM pvp_battles"),
    queryOne<{total: string}>("SELECT SUM(yen) as total FROM players"),
    query<{character_id: string; cnt: string; name: string}>(
      "SELECT p.character_id, COUNT(*) as cnt, c.name FROM players p LEFT JOIN characters c ON p.character_id=c.id WHERE p.character_id IS NOT NULL GROUP BY p.character_id, c.name ORDER BY cnt DESC LIMIT 5"
    ),
    query<{rank: string; cnt: string}>("SELECT rank, COUNT(*) as cnt FROM players GROUP BY rank ORDER BY cnt DESC"),
  ]);

  const rankDistObj: Record<string, number> = {};
  for (const r of rankDist) rankDistObj[r.rank] = Number(r.cnt);

  res.json({
    total_players: Number(totalPlayers?.cnt ?? 0),
    active_today: Number(activePlayers?.cnt ?? 0),
    total_battles: Number(totalBattles?.cnt ?? 0),
    total_yen_in_circulation: Number(totalYen?.total ?? 0),
    new_players_today: Number(newToday?.cnt ?? 0),
    top_characters: topChars.map(r => ({ character_id: r.character_id, name: r.name, count: Number(r.cnt) })),
    rank_distribution: rankDistObj,
  });
});

router.get("/admin/logs", requireAuth, requireAdmin, async (req, res): Promise<void> => {
  const limit = Math.min(200, Number(req.query.limit ?? 50));
  const rows = await query<Record<string, unknown>>(
    `SELECT al.*, pa.display_name as admin_name, pt.display_name as target_name
     FROM audit_logs al
     LEFT JOIN players pa ON al.admin_id=pa.user_id
     LEFT JOIN players pt ON al.target_user_id=pt.user_id
     ORDER BY al.created_at DESC LIMIT $1`,
    [limit]
  );
  res.json(rows.map(r => ({
    id: Number(r.id),
    admin_id: Number(r.admin_id),
    admin_name: r.admin_name as string | null ?? null,
    target_user_id: r.target_user_id ? Number(r.target_user_id) : null,
    target_name: r.target_name as string | null ?? null,
    action: String(r.action),
    data: r.data ?? {},
    created_at: String(r.created_at),
  })));
});

export default router;
