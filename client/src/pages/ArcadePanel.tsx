import { useState } from 'react';
import { Crosshair, Flame, Gamepad2, Loader2, Sparkles, Trophy } from 'lucide-react';
import { jjkApi } from '@/lib/jjk-api';

type Props = { onBalanceChange?: (yen: number) => void };
const games = [
  { id: 'curse_hunt', name: 'Curse Hunt', detail: 'Track a cursed signature', icon: Crosshair, accent: '#55d8e5' },
  { id: 'domain_dash', name: 'Domain Dash', detail: 'Escape the collapsing barrier', icon: Sparkles, accent: '#ab75ff' },
  { id: 'black_flash', name: 'Black Flash Timing', detail: 'Hit the perfect impact window', icon: Flame, accent: '#ef5b68' },
];

export default function ArcadePanel({ onBalanceChange }: Props) {
  const [playing, setPlaying] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  async function play(gameId: string) {
    if (playing) return;
    setPlaying(gameId); setError(''); setMessage('');
    try { const result = await jjkApi.arcade(gameId); onBalanceChange?.(result.balance); setMessage(`${result.message} · ${result.reward ? `¥${result.reward.toLocaleString()} earned` : 'No yen this run'}.`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Arcade unavailable.'); }
    finally { setPlaying(''); }
  }
  return <section className="panel arcade-glow mt-5 p-6 sm:p-8" aria-label="Yen arcade">
    <div className="relative flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="mb-2 flex items-center gap-2"><Gamepad2 size={15} className="text-[#ffd166]" /><p className="eyebrow text-[#ffd166]">Arcade // earn yen</p></div><h2 className="font-display text-2xl font-semibold sm:text-3xl">Make your next move count.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-[#9aa7bc]">Three server-settled missions. Skill beats luck. Each run has a short cooldown so the economy stays healthy.</p></div><div className="flex items-center gap-2 border border-[#ffd166]/25 bg-[#ffd166]/10 px-4 py-3 text-xs text-[#ffe29a]"><Trophy size={15} /> Rewards go straight to yen</div></div>
    <div className="relative mt-7 grid gap-3 lg:grid-cols-3">{games.map(({ id, name, detail, icon: Icon, accent }) => <button key={id} type="button" onClick={() => void play(id)} disabled={Boolean(playing)} className="group border border-white/10 bg-[#080e18]/70 p-5 text-left transition hover:-translate-y-1 hover:border-white/30 disabled:cursor-wait disabled:opacity-70"><div className="flex items-start justify-between"><span className="flex h-10 w-10 items-center justify-center border" style={{ color: accent, borderColor: `${accent}55`, background: `${accent}12` }}><Icon size={18} /></span>{playing === id && <Loader2 size={16} className="animate-spin text-[#55d8e5]" />}</div><p className="mt-5 font-display text-lg font-semibold">{name}</p><p className="mt-1 text-xs leading-5 text-[#8795aa]">{detail}</p><span className="mt-5 inline-flex border-t border-white/10 pt-3 text-[10px] font-semibold uppercase tracking-[.16em] text-[#d7dfed]">Run mission →</span></button>)}</div>
    {(message || error) && <p role={error ? 'alert' : 'status'} className={`relative mt-4 border p-3 text-xs ${error ? 'border-[#f05b63]/30 bg-[#f05b63]/10 text-[#ffafb3]' : 'border-[#9be15d]/30 bg-[#9be15d]/10 text-[#c8f69f]'}`}>{message || error}</p>}
  </section>;
}
