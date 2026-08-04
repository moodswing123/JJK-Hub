import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

router.get("/daily/status", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const row = await queryOne<{last_daily: string | null}>("SELECT last_daily FROM players WHERE user_id=$1", [userId]);
  const lastDaily = row?.last_daily ? new Date(row.last_daily) : null;
  const now = new Date();
  const canClaim = !lastDaily || (now.getTime() - lastDaily.getTime()) > 24 * 60 * 60 * 1000;
  const nextClaimAt = lastDaily ? new Date(lastDaily.getTime() + 24 * 60 * 60 * 1000).toISOString() : null;

  res.json({
    can_claim: canClaim,
    next_claim_at: nextClaimAt,
    streak: 1,
    last_claimed_at: row?.last_daily ?? null,
  });
});

router.post("/daily/claim", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const row = await queryOne<{last_daily: string | null}>("SELECT last_daily FROM players WHERE user_id=$1", [userId]);
  const lastDaily = row?.last_daily ? new Date(row.last_daily) : null;
  const now = new Date();

  if (lastDaily && (now.getTime() - lastDaily.getTime()) < 24 * 60 * 60 * 1000) {
    res.status(400).json({ error: "Already claimed today" });
    return;
  }

  const yenReward = 1000;
  const xpReward = 100;

  await query(
    "UPDATE players SET yen=yen+$1, xp=xp+$2, last_daily=$3 WHERE user_id=$4",
    [yenReward, xpReward, now.toISOString(), userId]
  );

  await query(
    "INSERT INTO notifications (user_id, type, title, message) VALUES ($1,'reward','Daily Reward Claimed',$2)",
    [userId, `You claimed your daily reward: +¥${yenReward.toLocaleString()} and +${xpReward} XP!`]
  );

  res.json({ yen: yenReward, xp: xpReward, streak: 1, bonus_item: null });
});

export default router;
