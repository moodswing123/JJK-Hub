import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query } from "../lib/db";

const router: IRouter = Router();

router.get("/announcements", requireAuth, async (_req, res): Promise<void> => {
  const rows = await query<Record<string, unknown>>(
    `SELECT a.*, p.display_name as author_name
     FROM announcements a LEFT JOIN players p ON a.author_id=p.user_id
     ORDER BY a.pinned DESC, a.created_at DESC LIMIT 20`
  );
  res.json(rows.map(r => ({
    id: Number(r.id),
    title: String(r.title),
    content: String(r.content),
    author_id: r.author_id ? Number(r.author_id) : null,
    author_name: r.author_name as string | null ?? null,
    pinned: r.pinned === true,
    created_at: String(r.created_at),
  })));
});

export default router;
