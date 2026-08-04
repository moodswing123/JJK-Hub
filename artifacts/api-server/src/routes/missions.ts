import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

router.get("/missions/daily", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const today = new Date().toISOString().split("T")[0];

  const existing = await query<Record<string, unknown>>(
    "SELECT * FROM missions WHERE user_id=$1 AND date=$2",
    [userId, today]
  );

  if (existing.length > 0) {
    res.json(existing.map(formatMission));
    return;
  }

  const defaults = [
    { name: "Spirit Exorcist", description: "Defeat 3 cursed spirits in battle", mission_type: "battle_wins", target_value: 3, reward_yen: 2000, reward_xp: 150 },
    { name: "Wealthy Sorcerer", description: "Earn 5000 yen from battles", mission_type: "yen_earned", target_value: 5000, reward_yen: 1000, reward_xp: 100 },
    { name: "PvP Champion", description: "Win 2 PvP battles", mission_type: "pvp_wins", target_value: 2, reward_yen: 3000, reward_xp: 200 },
    { name: "Technique Master", description: "Use techniques 5 times in battle", mission_type: "technique_uses", target_value: 5, reward_yen: 1500, reward_xp: 100 },
  ];

  for (const m of defaults) {
    await query(
      "INSERT INTO missions (user_id,name,description,mission_type,target_value,current_value,reward_yen,reward_xp,completed,date) VALUES ($1,$2,$3,$4,$5,0,$6,$7,0,$8)",
      [userId, m.name, m.description, m.mission_type, m.target_value, m.reward_yen, m.reward_xp, today]
    );
  }

  const fresh = await query<Record<string, unknown>>(
    "SELECT * FROM missions WHERE user_id=$1 AND date=$2",
    [userId, today]
  );
  res.json(fresh.map(formatMission));
});

function formatMission(r: Record<string, unknown>) {
  return {
    id: Number(r.id),
    name: String(r.name),
    description: String(r.description),
    mission_type: String(r.mission_type),
    target_value: Number(r.target_value),
    current_value: Number(r.current_value),
    reward_yen: Number(r.reward_yen),
    reward_xp: Number(r.reward_xp),
    completed: Number(r.completed),
    date: r.date as string | null,
  };
}

export default router;
