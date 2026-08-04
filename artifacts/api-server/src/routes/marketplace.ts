import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

router.get("/marketplace/listings", requireAuth, async (req, res): Promise<void> => {
  const limit = Math.min(100, Number(req.query.limit ?? 50));
  const typeFilter = req.query.type as string | undefined;

  let sql = `SELECT ml.*, p.display_name as seller_name, si.name as item_name, si.type as item_type
             FROM marketplace_listings ml
             JOIN players p ON ml.seller_id=p.user_id
             JOIN shop_items si ON ml.item_id=si.id
             WHERE ml.status='active'`;
  const params: unknown[] = [limit];
  if (typeFilter) { sql += ` AND si.type=$2`; params.push(typeFilter); params[0] = limit; }
  sql += ` ORDER BY ml.created_at DESC LIMIT $1`;

  const rows = await query<Record<string, unknown>>(sql, params);
  res.json(rows.map(r => ({
    id: Number(r.id),
    seller_id: Number(r.seller_id),
    seller_name: String(r.seller_name),
    item_id: Number(r.item_id),
    item_name: String(r.item_name),
    item_type: String(r.item_type),
    price: Number(r.price),
    quantity: Number(r.quantity),
    status: String(r.status),
    created_at: String(r.created_at),
  })));
});

router.post("/marketplace/listings", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { item_id, price, quantity = 1 } = req.body;
  if (!item_id || !price) { res.status(400).json({ error: "item_id and price required" }); return; }

  const invRow = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  let inv: number[] = [];
  try { inv = JSON.parse(invRow?.inventory ?? "[]"); } catch { inv = []; }

  if (!inv.includes(Number(item_id))) {
    res.status(400).json({ error: "Item not in inventory" }); return;
  }

  const item = await queryOne<{name: string, type: string}>("SELECT name, type FROM shop_items WHERE id=$1", [item_id]);
  if (!item) { res.status(404).json({ error: "Item not found" }); return; }

  // Remove from inventory
  const idx = inv.indexOf(Number(item_id));
  inv.splice(idx, 1);
  await query("UPDATE players SET inventory=$1 WHERE user_id=$2", [JSON.stringify(inv), userId]);

  const [listing] = await query<Record<string, unknown>>(
    "INSERT INTO marketplace_listings (seller_id, item_id, price, quantity) VALUES ($1,$2,$3,$4) RETURNING *",
    [userId, item_id, price, quantity]
  );
  const sellerRow = await queryOne<{display_name: string}>("SELECT display_name FROM players WHERE user_id=$1", [userId]);

  res.status(201).json({
    id: Number(listing.id),
    seller_id: userId,
    seller_name: sellerRow?.display_name ?? "Unknown",
    item_id: Number(item_id),
    item_name: item.name,
    item_type: item.type,
    price: Number(price),
    quantity: Number(quantity),
    status: "active",
    created_at: String(listing.created_at),
  });
});

router.delete("/marketplace/listings/:id", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw, 10);

  const listing = await queryOne<Record<string, unknown>>(
    "SELECT * FROM marketplace_listings WHERE id=$1 AND seller_id=$2 AND status='active'",
    [id, userId]
  );
  if (!listing) { res.status(404).json({ error: "Listing not found" }); return; }

  await query("UPDATE marketplace_listings SET status='cancelled' WHERE id=$1", [id]);

  // Return item to inventory
  const invRow = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  let inv: number[] = [];
  try { inv = JSON.parse(invRow?.inventory ?? "[]"); } catch { inv = []; }
  inv.push(Number(listing.item_id));
  await query("UPDATE players SET inventory=$1 WHERE user_id=$2", [JSON.stringify(inv), userId]);

  res.sendStatus(204);
});

router.post("/marketplace/listings/:id/buy", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const raw = Array.isArray(req.params.id) ? req.params.id[0] : req.params.id;
  const id = parseInt(raw, 10);

  const listing = await queryOne<Record<string, unknown>>(
    "SELECT ml.*, si.name as item_name FROM marketplace_listings ml JOIN shop_items si ON ml.item_id=si.id WHERE ml.id=$1 AND ml.status='active'",
    [id]
  );
  if (!listing) { res.status(404).json({ error: "Listing not found or already sold" }); return; }
  if (Number(listing.seller_id) === userId) { res.status(400).json({ error: "Cannot buy your own listing" }); return; }

  const price = Number(listing.price);
  const buyerRow = await queryOne<{yen: number}>("SELECT yen FROM players WHERE user_id=$1", [userId]);
  if (!buyerRow || buyerRow.yen < price) {
    res.status(400).json({ error: "Insufficient Yen" }); return;
  }

  // Transfer yen
  await query("UPDATE players SET yen=yen-$1 WHERE user_id=$2", [price, userId]);
  await query("UPDATE players SET yen=yen+$1 WHERE user_id=$2", [Math.floor(price * 0.95), listing.seller_id]);
  await query("UPDATE marketplace_listings SET status='sold' WHERE id=$1", [id]);

  // Add item to buyer's inventory
  const invRow = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  let inv: number[] = [];
  try { inv = JSON.parse(invRow?.inventory ?? "[]"); } catch { inv = []; }
  inv.push(Number(listing.item_id));
  await query("UPDATE players SET inventory=$1 WHERE user_id=$2", [JSON.stringify(inv), userId]);

  const newYen = await queryOne<{yen: number}>("SELECT yen FROM players WHERE user_id=$1", [userId]);

  // Notify seller
  await query(
    "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'trade','Item Sold',$2)",
    [listing.seller_id, `Your ${listing.item_name} sold for ¥${Math.floor(price * 0.95).toLocaleString()}`]
  );

  res.json({
    success: true,
    message: `Purchased ${listing.item_name} for ¥${price.toLocaleString()}`,
    new_yen: newYen?.yen ?? 0,
    item: null,
  });
});

export default router;
