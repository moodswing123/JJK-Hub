import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";
import { buildPlayer } from "./auth";

const router: IRouter = Router();

const PREMIUM_PACKS = [
  // Yen packs
  { id: "yen-100k", name: "Cursed Energy Pack", description: "100,000 Yen to power your battles", price_usd: 1.99, category: "yen", yen_amount: 100000, elixir_amount: null, bonus_label: null, discount_pct: null, is_featured: false, image_url: null },
  { id: "yen-500k", name: "Sorcerer Pack", description: "500,000 Yen + 5% bonus", price_usd: 8.99, category: "yen", yen_amount: 525000, elixir_amount: null, bonus_label: "+5% Bonus", discount_pct: null, is_featured: false, image_url: null },
  { id: "yen-1m", name: "Grade 1 Pack", description: "1 Million Yen + 10% bonus", price_usd: 15.99, category: "yen", yen_amount: 1100000, elixir_amount: null, bonus_label: "+10% Bonus", discount_pct: null, is_featured: true, image_url: null },
  { id: "yen-5m", name: "Special Grade Pack", description: "5 Million Yen + 15% bonus", price_usd: 69.99, category: "yen", yen_amount: 5750000, elixir_amount: null, bonus_label: "+15% Bonus", discount_pct: 10, is_featured: false, image_url: null },
  { id: "yen-10m", name: "Gojo Pack", description: "10 Million Yen + 20% bonus", price_usd: 129.99, category: "yen", yen_amount: 12000000, elixir_amount: null, bonus_label: "+20% Bonus", discount_pct: 15, is_featured: true, image_url: null },
  { id: "yen-20m", name: "Sukuna Pack", description: "20 Million Yen + 25% bonus", price_usd: 229.99, category: "yen", yen_amount: 25000000, elixir_amount: null, bonus_label: "+25% Bonus", discount_pct: 20, is_featured: false, image_url: null },
  // Elixir packs
  { id: "elix-10", name: "Cursed Drop", description: "10 Elixirs for XP boosts", price_usd: 2.99, category: "elixir", yen_amount: null, elixir_amount: 10, bonus_label: null, discount_pct: null, is_featured: false, image_url: null },
  { id: "elix-50", name: "Soul Vial", description: "50 Elixirs + 5 bonus", price_usd: 12.99, category: "elixir", yen_amount: null, elixir_amount: 55, bonus_label: "+5 Bonus", discount_pct: null, is_featured: false, image_url: null },
  { id: "elix-250", name: "Mahoraga Essence", description: "250 Elixirs + 25 bonus", price_usd: 54.99, category: "elixir", yen_amount: null, elixir_amount: 275, bonus_label: "+25 Bonus", discount_pct: 10, is_featured: true, image_url: null },
  { id: "elix-1000", name: "Limitless Vial", description: "1000 Elixirs — ultimate power", price_usd: 199.99, category: "elixir", yen_amount: null, elixir_amount: 1200, bonus_label: "+200 Bonus", discount_pct: 20, is_featured: false, image_url: null },
  // Bundles
  { id: "bundle-starter", name: "Starter Pack", description: "500,000 Yen + 25 Elixirs + Heal Potion x3", price_usd: 9.99, category: "bundle", yen_amount: 500000, elixir_amount: 25, bonus_label: "Includes Heal Potions", discount_pct: 20, is_featured: false, image_url: null },
  { id: "bundle-legend", name: "Legend Pack", description: "5M Yen + 100 Elixirs + Grade Upgrade Token", price_usd: 79.99, category: "bundle", yen_amount: 5000000, elixir_amount: 100, bonus_label: "Grade Upgrade Token", discount_pct: 25, is_featured: true, image_url: null },
  { id: "bundle-special-grade", name: "Special Grade Bundle", description: "10M Yen + 250 Elixirs + Domain Blueprint", price_usd: 149.99, category: "bundle", yen_amount: 10000000, elixir_amount: 250, bonus_label: "Domain Expansion Blueprint", discount_pct: 30, is_featured: false, image_url: null },
  { id: "bundle-vip", name: "VIP Bundle", description: "20M Yen + 500 Elixirs + Gojo Character + 5 Rare Items", price_usd: 279.99, category: "bundle", yen_amount: 20000000, elixir_amount: 500, bonus_label: "Gojo Character Unlock", discount_pct: 35, is_featured: true, image_url: null },
];

router.get("/shop/items", requireAuth, async (_req, res): Promise<void> => {
  const rows = await query<Record<string, unknown>>("SELECT * FROM shop_items ORDER BY type, price");
  res.json(rows.map(r => ({
    id: Number(r.id),
    name: String(r.name),
    description: String(r.description),
    price: Number(r.price),
    type: String(r.type),
    effect: r.effect as string | null,
    image_url: r.image_url as string | null,
    use_description: r.use_description as string | null,
  })));
});

router.get("/shop/packs", requireAuth, async (_req, res): Promise<void> => {
  res.json(PREMIUM_PACKS);
});

router.post("/shop/purchase", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { item_id } = req.body;
  if (!item_id) { res.status(400).json({ error: "item_id required" }); return; }

  const item = await queryOne<Record<string, unknown>>("SELECT * FROM shop_items WHERE id=$1", [item_id]);
  if (!item) { res.status(404).json({ error: "Item not found" }); return; }

  const player = await queryOne<{yen: number}>("SELECT yen FROM players WHERE user_id=$1", [userId]);
  if (!player) { res.status(404).json({ error: "Player not found" }); return; }

  const price = Number(item.price);
  if (player.yen < price) {
    res.status(400).json({ error: `Insufficient Yen. Need ${price.toLocaleString()}, have ${player.yen.toLocaleString()}` });
    return;
  }

  // Deduct yen and add to inventory
  const [updated] = await query<{yen: number}>(
    "UPDATE players SET yen=yen-$1 WHERE user_id=$2 RETURNING yen",
    [price, userId]
  );

  const existing = await queryOne<{inventory: string}>("SELECT inventory FROM players WHERE user_id=$1", [userId]);
  let inv: number[] = [];
  try { inv = JSON.parse(existing?.inventory ?? "[]"); } catch { inv = []; }
  inv.push(Number(item_id));
  await query("UPDATE players SET inventory=$1 WHERE user_id=$2", [JSON.stringify(inv), userId]);

  // Create notification
  await query(
    "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'purchase','Item Purchased',$2)",
    [userId, `You purchased ${item.name} for ¥${price.toLocaleString()}`]
  );

  res.json({
    success: true,
    message: `Successfully purchased ${item.name}`,
    new_yen: updated.yen,
    item: {
      id: Number(item.id),
      name: String(item.name),
      description: String(item.description),
      price,
      type: String(item.type),
      effect: item.effect as string | null,
      image_url: item.image_url as string | null,
      use_description: item.use_description as string | null,
    },
  });
});

export default router;
