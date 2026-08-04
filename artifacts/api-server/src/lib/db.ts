import pg from "pg";
import { logger } from "./logger";

const { Pool } = pg;

const postgresUrl = process.env.POSTGRES_URL;
if (!postgresUrl) {
  throw new Error("POSTGRES_URL must be set. Add it as a Secret.");
}

export const pool = new Pool({
  connectionString: postgresUrl,
  ssl: { rejectUnauthorized: false },
  max: 10,
});

pool.on("error", (err) => {
  logger.error({ err }, "Unexpected pool error");
});

export async function query<T extends Record<string, unknown> = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
): Promise<T[]> {
  const client = await pool.connect();
  try {
    const res = await client.query(sql, params);
    return res.rows as T[];
  } finally {
    client.release();
  }
}

export async function queryOne<T extends Record<string, unknown> = Record<string, unknown>>(
  sql: string,
  params?: unknown[]
): Promise<T | null> {
  const rows = await query<T>(sql, params);
  return rows[0] ?? null;
}

/** Initialize all dashboard-specific tables */
export async function initDashboardTables(): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS dashboard_profiles (
        user_id BIGINT PRIMARY KEY,
        avatar_url TEXT,
        banner_url TEXT,
        bio TEXT,
        equipped_title TEXT,
        equipped_badge TEXT,
        equipped_frame TEXT,
        theme TEXT DEFAULT 'dark',
        elixirs INTEGER DEFAULT 0,
        is_admin BOOLEAN DEFAULT false,
        is_banned BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        type TEXT NOT NULL,
        amount NUMERIC NOT NULL DEFAULT 0,
        currency TEXT NOT NULL DEFAULT 'USD',
        yen_amount INTEGER,
        elixir_amount INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        provider TEXT,
        provider_tx_id TEXT,
        admin_note TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        type TEXT NOT NULL DEFAULT 'info',
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        read BOOLEAN DEFAULT false,
        data JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read)`);

    await client.query(`
      CREATE TABLE IF NOT EXISTS announcements (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        author_id BIGINT,
        pinned BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS casino_sessions (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        game TEXT NOT NULL,
        bet INTEGER NOT NULL,
        won BOOLEAN NOT NULL,
        payout INTEGER NOT NULL DEFAULT 0,
        details JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);
    await client.query(`CREATE INDEX IF NOT EXISTS idx_casino_user ON casino_sessions(user_id)`);

    await client.query(`
      CREATE TABLE IF NOT EXISTS marketplace_listings (
        id SERIAL PRIMARY KEY,
        seller_id BIGINT NOT NULL,
        item_id INTEGER NOT NULL,
        price INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        admin_id BIGINT NOT NULL,
        target_user_id BIGINT,
        action TEXT NOT NULL,
        data JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT NOW()
      )
    `);

    // Seed a default announcement if none exist
    const ann = await client.query("SELECT id FROM announcements LIMIT 1");
    if (ann.rows.length === 0) {
      await client.query(
        `INSERT INTO announcements (title, content, pinned) VALUES ($1, $2, true)`,
        [
          "Welcome to the JJK RPG Dashboard!",
          "Manage your sorcerer, claim daily rewards, battle in the casino, and trade in the marketplace. The dashboard syncs with your Telegram bot in real-time. Contact @victory_tech for manual Yen purchases.",
        ]
      );
    }

    logger.info("Dashboard tables initialized");
  } finally {
    client.release();
  }
}
