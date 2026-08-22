// Obsidian Command Deck: typed, explicit data access keeps Telegram identity and player telemetry reliable.

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export type Player = {
  user_id: number;
  username: string | null;
  display_name: string;
  level: number;
  rank: string;
  xp: number;
  xp_needed: number;
  yen: number;
  hp: number;
  max_hp: number;
  cursed_energy: number;
  max_cursed_energy: number;
  attack: number;
  defense: number;
  speed: number;
  wins: number;
  losses: number;
  win_rate: number;
  avatar_url?: string | null;
  equipped_title?: string | null;
  domain_name?: string | null;
  is_admin?: boolean;
};

export type TelegramUser = { id: number; first_name: string; last_name?: string | null; username?: string | null; photo_url?: string | null; auth_date: number; hash: string };
export type Activity = { id: number | string; message: string; created_at: string };
export type Summary = { player: Player; online_count: number; recent_activity: Activity[]; announcements?: { title: string; content: string }[]; daily_status?: { streak?: number; can_claim?: boolean } };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem('jjk_token');
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.error || `Request failed with status ${response.status}`);
  return payload as T;
}

export const jjkApi = {
  telegramLogin: (user: TelegramUser) => request<{ token: string; player: Player }>('/auth/telegram', { method: 'POST', body: JSON.stringify(user) }),
  passwordLogin: (username: string, password: string) => request<{ token: string; player: Player }>('/auth/password', { method: 'POST', body: JSON.stringify({ username, password }) }),
  passwordReset: (username: string, code: string, newPassword: string) => request<{ success: boolean }>('/auth/password-reset', { method: 'POST', body: JSON.stringify({ username, code, new_password: newPassword }) }),
  me: () => request<Player>('/auth/me'),
  summary: () => request<Summary>('/dashboard/summary'),
  logout: () => request<{ success: boolean }>('/auth/logout', { method: 'POST' }),
};
