import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

function parseChar(row: Record<string, unknown>) {
  let attacks: unknown[] = [];
  try { attacks = JSON.parse(String(row.attacks ?? "[]")); } catch { attacks = []; }
  return {
    id: Number(row.id),
    name: String(row.name),
    grade: String(row.grade),
    quote: row.quote as string | null,
    technique: String(row.technique),
    attack: Number(row.attack),
    defense: Number(row.defense),
    speed: Number(row.speed),
    max_hp: Number(row.max_hp),
    max_ce: Number(row.max_ce),
    cost: Number(row.cost ?? 0),
    image_url: row.image_url as string | null,
    attacks,
  };
}

router.get("/characters", requireAuth, async (_req, res): Promise<void> => {
  const rows = await query<Record<string, unknown>>("SELECT * FROM characters ORDER BY id");
  res.json(rows.map(parseChar));
});

router.get("/characters/:id", requireAuth, async (req, res): Promise<void> => {
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw, 10);
  const row = await queryOne<Record<string, unknown>>("SELECT * FROM characters WHERE id=$1", [id]);
  if (!row) { res.status(404).json({ error: "Character not found" }); return; }
  res.json(parseChar(row));
});

export default router;
