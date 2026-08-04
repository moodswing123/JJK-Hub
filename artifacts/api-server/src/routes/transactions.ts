import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

function formatTx(r: Record<string, unknown>) {
  return {
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
  };
}

router.get("/transactions", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const limit = Math.min(100, Number(req.query.limit ?? 20));
  const rows = await query<Record<string, unknown>>(
    "SELECT t.*, p.display_name FROM transactions t LEFT JOIN players p ON t.user_id=p.user_id WHERE t.user_id=$1 ORDER BY t.created_at DESC LIMIT $2",
    [userId, limit]
  );
  res.json(rows.map(formatTx));
});

router.post("/transactions/manual", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { yen_amount, contact_note } = req.body;
  if (!yen_amount || yen_amount < 1000) {
    res.status(400).json({ error: "Minimum manual purchase is 1,000 Yen" }); return;
  }

  const [tx] = await query<Record<string, unknown>>(
    `INSERT INTO transactions (user_id, type, amount, currency, yen_amount, status, provider, admin_note)
     VALUES ($1,'manual_yen',0,'MANUAL',$2,'pending','manual',$3) RETURNING *`,
    [userId, yen_amount, contact_note ?? null]
  );

  // Notify admins (create notification for the owner)
  const ownerId = Number(process.env.OWNER_ID ?? 0);
  if (ownerId) {
    const player = await queryOne<{display_name: string}>("SELECT display_name FROM players WHERE user_id=$1", [userId]);
    await query(
      "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'purchase','Manual Purchase Request',$2)",
      [ownerId, `${player?.display_name ?? userId} requested ¥${Number(yen_amount).toLocaleString()} manual purchase. Contact @victory_tech`]
    );
  }

  res.status(201).json({
    id: Number(tx.id),
    user_id: userId,
    yen_amount: Number(yen_amount),
    contact_note: contact_note ?? null,
    status: "pending",
    admin_note: null,
    created_at: String(tx.created_at),
    updated_at: null,
  });
});

router.get("/transactions/manual/list", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const rows = await query<Record<string, unknown>>(
    "SELECT * FROM transactions WHERE user_id=$1 AND type='manual_yen' ORDER BY created_at DESC",
    [userId]
  );
  res.json(rows.map(r => ({
    id: Number(r.id),
    user_id: Number(r.user_id),
    yen_amount: r.yen_amount ? Number(r.yen_amount) : null,
    contact_note: r.admin_note as string | null,
    status: String(r.status),
    admin_note: r.admin_note as string | null,
    created_at: String(r.created_at),
    updated_at: r.updated_at ? String(r.updated_at) : null,
  })));
});

export default router;
