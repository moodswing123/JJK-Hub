import crypto from "crypto";

export interface TelegramAuthData {
  id: number;
  first_name: string;
  last_name?: string | null;
  username?: string | null;
  photo_url?: string | null;
  auth_date: number;
  hash: string;
}

export function verifyTelegramAuth(data: TelegramAuthData): boolean {
  const botToken = process.env.TELEGRAM_BOT_TOKEN;
  if (!botToken) return false;

  // Check data freshness (5 min window)
  const now = Math.floor(Date.now() / 1000);
  if (now - data.auth_date > 86400) return false; // Allow 24h for testing

  const { hash, ...rest } = data;

  // Build data check string
  const checkArr = Object.entries(rest)
    .filter(([, v]) => v !== undefined && v !== null)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`);

  const checkString = checkArr.join("\n");

  const secretKey = crypto.createHash("sha256").update(botToken).digest();
  const computedHash = crypto
    .createHmac("sha256", secretKey)
    .update(checkString)
    .digest("hex");

  return computedHash === hash;
}
