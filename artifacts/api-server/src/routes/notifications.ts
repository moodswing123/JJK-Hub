import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

function formatNotif(r: Record<string, unknown>) {
  return {
    id: Number(r.id),
    user_id: Number(r.user_id),
    type: String(r.type),
    title: String(r.title),
    message: String(r.message),
    read: r.read === true,
    created_at: String(r.created_at),
  };
}

router.get("/notifications", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const rows = await query<Record<string, unknown>>(
    "SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50",
    [userId]
  );
  res.json(rows.map(formatNotif));
});

router.patch("/notifications/:id/read", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw, 10);

  const [row] = await query<Record<string, unknown>>(
    "UPDATE notifications SET read=true WHERE id=$1 AND user_id=$2 RETURNING *",
    [id, userId]
  );
  if (!row) { res.status(404).json({ error: "Notification not found" }); return; }
  res.json(formatNotif(row));
});

router.post("/notifications/read-all", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  await query("UPDATE notifications SET read=true WHERE user_id=$1", [userId]);
  res.json({ success: true, message: "All notifications marked as read" });
});

export default router;
