import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

router.get("/inventory", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const row = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  if (!row) { res.json([]); return; }

  let invIds: number[] = [];
  try { invIds = JSON.parse(row.inventory ?? "[]"); } catch { invIds = []; }

  if (invIds.length === 0) { res.json([]); return; }

  const counts: Record<number, number> = {};
  for (const id of invIds) counts[id] = (counts[id] ?? 0) + 1;

  const uniqueIds = [...new Set(invIds)];
  if (uniqueIds.length === 0) { res.json([]); return; }

  const placeholders = uniqueIds.map((_, i) => `$${i + 1}`).join(",");
  const items = await query<Record<string, unknown>>(
    `SELECT * FROM shop_items WHERE id IN (${placeholders})`,
    uniqueIds
  );

  res.json(items.map(item => ({
    id: Number(item.id),
    name: String(item.name),
    description: String(item.description),
    price: Number(item.price),
    type: String(item.type),
    effect: item.effect as string | null,
    image_url: item.image_url as string | null,
    use_description: item.use_description as string | null,
    quantity: counts[Number(item.id)] ?? 1,
  })));
});

router.post("/inventory/:itemId/use", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const raw = Array.isArray(req.params.itemId) ? req.params.itemId[0] : req.params.itemId;
  const itemId = parseInt(raw, 10);

  const invRow = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  let inv: number[] = [];
  try { inv = JSON.parse(invRow?.inventory ?? "[]"); } catch { inv = []; }

  const idx = inv.indexOf(itemId);
  if (idx === -1) { res.status(400).json({ error: "Item not in inventory" }); return; }

  const item = await queryOne<Record<string, unknown>>("SELECT * FROM shop_items WHERE id=$1", [itemId]);
  if (!item) { res.status(404).json({ error: "Item not found" }); return; }

  let effect: Record<string, number> = {};
  try { effect = JSON.parse(String(item.effect ?? "{}")); } catch { effect = {}; }

  const player = await queryOne<Record<string, unknown>>("SELECT * FROM players WHERE user_id=$1", [userId]);
  if (!player) { res.status(404).json({ error: "Player not found" }); return; }

  let hpGained = 0, ceGained = 0, xpGained = 0;
  const updates: string[] = [];
  const params: unknown[] = [];

  if (effect.hp) {
    const newHp = Math.min(Number(player.max_hp), Number(player.hp) + effect.hp);
    hpGained = newHp - Number(player.hp);
    updates.push(`hp=$${params.length + 1}`);
    params.push(newHp);
  }
  if (effect.ce) {
    const newCe = Math.min(Number(player.max_cursed_energy), Number(player.cursed_energy) + effect.ce);
    ceGained = newCe - Number(player.cursed_energy);
    updates.push(`cursed_energy=$${params.length + 1}`);
    params.push(newCe);
  }
  if (effect.xp) {
    xpGained = effect.xp;
    updates.push(`xp=xp+$${params.length + 1}`);
    params.push(xpGained);
  }

  if (updates.length > 0) {
    params.push(userId);
    await query(`UPDATE players SET ${updates.join(",")} WHERE user_id=$${params.length}`, params);
  }

  // Remove one instance from inventory
  inv.splice(idx, 1);
  await query("UPDATE players SET inventory=$1 WHERE user_id=$2", [JSON.stringify(inv), userId]);

  const updated = await queryOne<Record<string, unknown>>("SELECT hp, cursed_energy, xp FROM players WHERE user_id=$1", [userId]);

  await query(
    "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'item','Item Used',$2)",
    [userId, `Used ${item.name}: ${item.use_description ?? "Effect applied"}`]
  );

  res.json({
    success: true,
    message: `Used ${item.name} successfully`,
    hp_gained: hpGained || null,
    ce_gained: ceGained || null,
    xp_gained: xpGained || null,
    new_hp: updated ? Number(updated.hp) : null,
    new_ce: updated ? Number(updated.cursed_energy) : null,
    new_xp: updated ? Number(updated.xp) : null,
  });
});

router.post("/inventory/:itemId/equip", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const raw = Array.isArray(req.params.itemId) ? req.params.itemId[0] : req.params.itemId;
  const itemId = parseInt(raw, 10);

  const item = await queryOne<Record<string, unknown>>("SELECT * FROM shop_items WHERE id=$1", [itemId]);
  if (!item) { res.status(404).json({ error: "Item not found" }); return; }

  let effect: Record<string, number> = {};
  try { effect = JSON.parse(String(item.effect ?? "{}")); } catch { effect = {}; }

  const updates: string[] = [];
  const params: unknown[] = [];
  if (effect.attack) { updates.push(`attack=attack+$${params.length + 1}`); params.push(effect.attack); }
  if (effect.defense) { updates.push(`defense=defense+$${params.length + 1}`); params.push(effect.defense); }

  if (updates.length > 0) {
    params.push(userId);
    await query(`UPDATE players SET ${updates.join(",")} WHERE user_id=$${params.length}`, params);
  }

  res.json({
    success: true,
    message: `${item.name} equipped! Stats updated.`,
  });
});

router.delete("/inventory/:itemId/sell", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const raw = Array.isArray(req.params.itemId) ? req.params.itemId[0] : req.params.itemId;
  const itemId = parseInt(raw, 10);

  const invRow = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  let inv: number[] = [];
  try { inv = JSON.parse(invRow?.inventory ?? "[]"); } catch { inv = []; }

  const idx = inv.indexOf(itemId);
  if (idx === -1) { res.status(404).json({ error: "Item not in inventory" }); return; }

  const item = await queryOne<Record<string, unknown>>("SELECT * FROM shop_items WHERE id=$1", [itemId]);
  if (!item) { res.status(404).json({ error: "Item not found" }); return; }

  const sellPrice = Math.floor(Number(item.price) * 0.4);
  inv.splice(idx, 1);

  await query("UPDATE players SET inventory=$1, yen=yen+$2 WHERE user_id=$3", [JSON.stringify(inv), sellPrice, userId]);
  const updated = await queryOne<{yen: number}>("SELECT yen FROM players WHERE user_id=$1", [userId]);

  res.json({
    success: true,
    message: `Sold ${item.name} for ¥${sellPrice.toLocaleString()}`,
    yen_gained: sellPrice,
    new_yen: updated?.yen ?? 0,
  });
});

export default router;
