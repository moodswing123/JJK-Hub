import { Router, type IRouter } from "express";
import { requireAuth } from "../lib/auth";
import { query, queryOne } from "../lib/db";

const router: IRouter = Router();

const MIN_BET = 100;
const MAX_BET = 10_000_000;

async function deductBet(userId: number, bet: number): Promise<number | null> {
  const row = await queryOne<{yen: number}>("SELECT yen FROM players WHERE user_id=$1", [userId]);
  if (!row || row.yen < bet) return null;
  const [updated] = await query<{yen: number}>(
    "UPDATE players SET yen=yen-$1 WHERE user_id=$2 RETURNING yen",
    [bet, userId]
  );
  return updated.yen;
}

async function addPayout(userId: number, payout: number): Promise<number> {
  const [updated] = await query<{yen: number}>(
    "UPDATE players SET yen=yen+$1 WHERE user_id=$2 RETURNING yen",
    [payout, userId]
  );
  return updated.yen;
}

async function saveSession(userId: number, game: string, bet: number, won: boolean, payout: number, details: Record<string, unknown>) {
  await query(
    "INSERT INTO casino_sessions (user_id, game, bet, won, payout, details) VALUES ($1,$2,$3,$4,$5,$6)",
    [userId, game, bet, won, payout, JSON.stringify(details)]
  );
}

router.post("/casino/coinflip", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { bet, choice } = req.body;
  if (!bet || bet < MIN_BET) { res.status(400).json({ error: `Minimum bet is ¥${MIN_BET.toLocaleString()}` }); return; }
  if (bet > MAX_BET) { res.status(400).json({ error: `Maximum bet is ¥${MAX_BET.toLocaleString()}` }); return; }
  if (!["heads", "tails"].includes(choice)) { res.status(400).json({ error: "Choice must be heads or tails" }); return; }

  const yenAfterBet = await deductBet(userId, bet);
  if (yenAfterBet === null) { res.status(400).json({ error: "Insufficient Yen" }); return; }

  const result = Math.random() < 0.5 ? "heads" : "tails";
  const won = result === choice;
  const payout = won ? bet * 2 : 0;
  let newYen = yenAfterBet;
  if (won) newYen = await addPayout(userId, payout);

  await saveSession(userId, "coinflip", bet, won, payout, { choice, result });

  res.json({
    won,
    payout,
    new_yen: newYen,
    game: "coinflip",
    outcome_text: won ? `Landed ${result}! You win ¥${payout.toLocaleString()}` : `Landed ${result}. Better luck next time!`,
    details: { choice, result },
  });
});

router.post("/casino/dice", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { bet } = req.body;
  if (!bet || bet < MIN_BET) { res.status(400).json({ error: `Minimum bet is ¥${MIN_BET.toLocaleString()}` }); return; }

  const yenAfterBet = await deductBet(userId, bet);
  if (yenAfterBet === null) { res.status(400).json({ error: "Insufficient Yen" }); return; }

  const playerRoll = Math.floor(Math.random() * 6) + 1;
  const houseRoll = Math.floor(Math.random() * 6) + 1;
  const won = playerRoll > houseRoll;
  const tie = playerRoll === houseRoll;
  const payout = won ? bet * 2 : (tie ? bet : 0);
  let newYen = yenAfterBet;
  if (payout > 0) newYen = await addPayout(userId, payout);

  await saveSession(userId, "dice", bet, won || tie, payout, { playerRoll, houseRoll });

  res.json({
    won: won || tie,
    payout,
    new_yen: newYen,
    game: "dice",
    outcome_text: tie ? `Both rolled ${playerRoll} — Tie! Bet returned.` : (won ? `You rolled ${playerRoll} vs ${houseRoll}! You win ¥${payout.toLocaleString()}` : `You rolled ${playerRoll} vs ${houseRoll}. House wins.`),
    details: { playerRoll, houseRoll },
  });
});

router.post("/casino/slots", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { bet } = req.body;
  if (!bet || bet < MIN_BET) { res.status(400).json({ error: `Minimum bet is ¥${MIN_BET.toLocaleString()}` }); return; }

  const yenAfterBet = await deductBet(userId, bet);
  if (yenAfterBet === null) { res.status(400).json({ error: "Insufficient Yen" }); return; }

  const symbols = ["Gojo", "Sukuna", "Yuji", "Megumi", "Nobara", "Cherry", "Diamond", "Star"];
  const reels = [
    symbols[Math.floor(Math.random() * symbols.length)],
    symbols[Math.floor(Math.random() * symbols.length)],
    symbols[Math.floor(Math.random() * symbols.length)],
  ];

  const allMatch = reels[0] === reels[1] && reels[1] === reels[2];
  const twoMatch = reels[0] === reels[1] || reels[1] === reels[2] || reels[0] === reels[2];
  const isJackpot = allMatch && (reels[0] === "Gojo" || reels[0] === "Sukuna");

  let multiplier = 0;
  if (isJackpot) multiplier = 20;
  else if (allMatch) multiplier = 5;
  else if (twoMatch) multiplier = 2;

  const payout = Math.floor(bet * multiplier);
  const won = payout > 0;
  let newYen = yenAfterBet;
  if (payout > 0) newYen = await addPayout(userId, payout);

  await saveSession(userId, "slots", bet, won, payout, { reels, multiplier });

  const outcomeText = isJackpot ? `JACKPOT! ${reels.join(" | ")} — ¥${payout.toLocaleString()} won!`
    : allMatch ? `Three of a kind! ¥${payout.toLocaleString()} won!`
    : twoMatch ? `Two of a kind! ¥${payout.toLocaleString()} won!`
    : `${reels.join(" | ")} — No match. Better luck!`;

  res.json({ won, payout, new_yen: newYen, game: "slots", outcome_text: outcomeText, details: { reels, multiplier } });
});

router.post("/casino/roulette", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { bet, bet_type, bet_value } = req.body;
  if (!bet || bet < MIN_BET) { res.status(400).json({ error: `Minimum bet is ¥${MIN_BET.toLocaleString()}` }); return; }

  const yenAfterBet = await deductBet(userId, bet);
  if (yenAfterBet === null) { res.status(400).json({ error: "Insufficient Yen" }); return; }

  const number = Math.floor(Math.random() * 37); // 0-36
  const color = number === 0 ? "green" : (number % 2 === 0 ? "black" : "red");

  let won = false;
  let multiplier = 0;

  switch (bet_type) {
    case "red": won = color === "red"; multiplier = 2; break;
    case "black": won = color === "black"; multiplier = 2; break;
    case "even": won = number > 0 && number % 2 === 0; multiplier = 2; break;
    case "odd": won = number % 2 === 1; multiplier = 2; break;
    case "number": won = Number(bet_value) === number; multiplier = 36; break;
    default: won = color === "red"; multiplier = 2;
  }

  const payout = won ? Math.floor(bet * multiplier) : 0;
  let newYen = yenAfterBet;
  if (won) newYen = await addPayout(userId, payout);

  await saveSession(userId, "roulette", bet, won, payout, { number, color, bet_type, bet_value });

  res.json({
    won,
    payout,
    new_yen: newYen,
    game: "roulette",
    outcome_text: won ? `Ball landed on ${number} (${color})! You win ¥${payout.toLocaleString()}` : `Ball landed on ${number} (${color}). You lost.`,
    details: { number, color, bet_type, bet_value },
  });
});

router.post("/casino/crash", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const { bet } = req.body;
  if (!bet || bet < MIN_BET) { res.status(400).json({ error: `Minimum bet is ¥${MIN_BET.toLocaleString()}` }); return; }

  const yenAfterBet = await deductBet(userId, bet);
  if (yenAfterBet === null) { res.status(400).json({ error: "Insufficient Yen" }); return; }

  // Crash point between 1.0 and 10.0
  const crashPoint = Math.max(1.0, Math.random() < 0.5 ? 1 + Math.random() * 2 : 1 + Math.random() * 8);
  const cashoutAt = crashPoint * 0.7; // Player always cashes out at 70% of crash point
  const won = cashoutAt >= 1.5;
  const multiplier = won ? cashoutAt : 0;
  const payout = won ? Math.floor(bet * multiplier) : 0;
  let newYen = yenAfterBet;
  if (won) newYen = await addPayout(userId, payout);

  await saveSession(userId, "crash", bet, won, payout, { crashPoint: crashPoint.toFixed(2), cashoutAt: cashoutAt.toFixed(2) });

  res.json({
    won,
    payout,
    new_yen: newYen,
    game: "crash",
    outcome_text: won ? `Cashed out at ${cashoutAt.toFixed(2)}x before crash at ${crashPoint.toFixed(2)}x! ¥${payout.toLocaleString()} won!` : `Crashed at ${crashPoint.toFixed(2)}x — you lost!`,
    details: { crashPoint: Number(crashPoint.toFixed(2)), cashoutAt: Number(cashoutAt.toFixed(2)), multiplier },
  });
});

router.get("/casino/stats", requireAuth, async (req, res): Promise<void> => {
  const userId = req.user!.userId;
  const stats = await queryOne<Record<string, unknown>>(
    `SELECT COUNT(*) as total_games, SUM(CASE WHEN won THEN 1 ELSE 0 END) as total_won,
     SUM(CASE WHEN NOT won THEN 1 ELSE 0 END) as total_lost,
     SUM(bet) as total_wagered, SUM(payout) as total_payout, MAX(payout) as biggest_win
     FROM casino_sessions WHERE user_id=$1`,
    [userId]
  );
  const favoriteRow = await queryOne<{game: string}>(
    "SELECT game, COUNT(*) as cnt FROM casino_sessions WHERE user_id=$1 GROUP BY game ORDER BY cnt DESC LIMIT 1",
    [userId]
  );

  const totalGames = Number(stats?.total_games ?? 0);
  const totalWon = Number(stats?.total_won ?? 0);

  res.json({
    total_games: totalGames,
    total_won: totalWon,
    total_lost: Number(stats?.total_lost ?? 0),
    total_wagered: Number(stats?.total_wagered ?? 0),
    total_payout: Number(stats?.total_payout ?? 0),
    biggest_win: Number(stats?.biggest_win ?? 0),
    win_rate: totalGames > 0 ? Math.round((totalWon / totalGames) * 1000) / 10 : 0,
    favorite_game: favoriteRow?.game ?? null,
  });
});

export default router;
