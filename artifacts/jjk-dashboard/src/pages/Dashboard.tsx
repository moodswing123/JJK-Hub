import { motion } from 'framer-motion';
import { Activity, ArrowUpRight, Bell, Coins, HeartPulse, Shield, Sparkles, Swords, Trophy, Zap } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { Link } from 'wouter';
import { useGetDashboardSummary } from '@workspace/api-client-react';
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Progress } from '@/components/ui/core';

const percent = (value: number, max: number) => max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
const number = (value: number) => value.toLocaleString();

export default function Dashboard() {
  const { data: summary, isLoading, isError } = useGetDashboardSummary();
  if (isLoading) return <DashboardSkeleton />;
  if (isError || !summary) return <ErrorState />;

  const { player, online_count, recent_activity = [], announcements = [], daily_status } = summary;
  const stats = [
    { label: 'Attack', value: player.attack, icon: Swords, tone: 'text-primary' },
    { label: 'Defense', value: player.defense, icon: Shield, tone: 'text-accent' },
    { label: 'Speed', value: player.speed, icon: Zap, tone: 'text-amber-300' },
    { label: 'Battles won', value: player.wins, icon: Trophy, tone: 'text-emerald-300' },
  ];

  return <div className="space-y-8">
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="section-label mb-2">Welcome back, sorcerer</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Your realm at a glance</h1><p className="mt-2 max-w-xl text-sm text-muted-foreground">Track your progression, manage your arsenal, and stay ahead of the curse outbreak.</p></div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.8)]" /> {online_count} players active</div>
    </motion.div>

    <motion.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="relative overflow-hidden rounded-2xl border border-primary/20 bg-gradient-to-br from-primary/15 via-card to-card p-6 shadow-2xl shadow-black/20 sm:p-8">
      <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
      <div className="relative grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="flex items-start gap-4 sm:gap-6"><div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-primary/30 bg-background/70 text-2xl font-semibold text-primary sm:h-20 sm:w-20">{player.avatar_url ? <img src={player.avatar_url} alt="" className="h-full w-full object-cover" /> : player.display_name.charAt(0).toUpperCase()}</div><div className="min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2"><h2 className="truncate text-2xl font-semibold sm:text-3xl">{player.display_name}</h2><Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary">LVL {player.level}</Badge></div><p className="section-label">{player.rank} · {player.equipped_title || 'Unbound sorcerer'}</p><div className="mt-6 grid max-w-xl gap-3 sm:grid-cols-3"><Meter label="HP" value={player.hp} max={player.max_hp} color="bg-emerald-400" /><Meter label="Cursed energy" value={player.cursed_energy} max={player.max_cursed_energy} color="bg-accent" /><Meter label="Experience" value={player.xp} max={player.xp_needed} color="bg-primary" /></div></div></div>
        <div className="grid grid-cols-2 gap-3 sm:min-w-[280px]"><ValueTile label="Yen balance" value={`¥${number(player.yen)}`} icon={Coins} tone="text-amber-300" /><ValueTile label="Win rate" value={`${player.win_rate.toFixed(1)}%`} icon={Trophy} tone="text-emerald-300" /></div>
      </div>
    </motion.section>

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(({ label, value, icon: Icon, tone }, index) => <motion.div key={label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .05 }}><Card className="h-full"><CardContent className="flex items-center justify-between p-5"><div><p className="section-label mb-2">{label}</p><p className="text-2xl font-semibold">{number(value)}</p></div><div className={`rounded-xl bg-muted/70 p-3 ${tone}`}><Icon size={19} /></div></CardContent></Card></motion.div>)}</div>

    <div className="grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
      <Card><CardHeader className="flex-row items-center justify-between border-b border-border/60"><div><p className="section-label mb-1">Live feed</p><CardTitle>Recent activity</CardTitle></div><Link href="/transactions"><Button variant="ghost" size="sm">View history <ArrowUpRight size={14} className="ml-1" /></Button></Link></CardHeader><CardContent className="p-0">{recent_activity.length ? recent_activity.slice(0, 5).map((entry) => <div key={entry.id} className="flex gap-4 border-b border-border/50 px-6 py-4 last:border-0"><div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary shadow-[0_0_8px_hsl(var(--primary)/.8)]" /><div className="min-w-0"><p className="text-sm text-foreground/90">{entry.message}</p><p className="mt-1 text-xs text-muted-foreground">{formatDistanceToNow(new Date(entry.created_at), { addSuffix: true })}</p></div></div>) : <EmptyState icon={Activity} label="No activity yet" detail="Your next action will appear here." />}</CardContent></Card>
      <div className="space-y-6"><Card className="border-primary/20 bg-primary/5"><CardHeader><p className="section-label mb-1">Daily ritual</p><CardTitle className="flex items-center gap-2"><Sparkles size={18} className="text-primary" /> Keep your streak alive</CardTitle></CardHeader><CardContent><div className="mb-5 flex items-end justify-between"><div><p className="text-4xl font-semibold text-primary">{daily_status?.streak || 0}</p><p className="text-xs text-muted-foreground">consecutive days</p></div><HeartPulse size={36} className="text-primary/40" /></div><Link href="/daily"><Button className="w-full">{daily_status?.can_claim ? 'Claim today’s reward' : 'View daily missions'}</Button></Link></CardContent></Card>{announcements[0] && <Card><CardHeader><p className="section-label mb-1">Realm bulletin</p><CardTitle className="flex items-center gap-2"><Bell size={17} /> {announcements[0].title}</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-muted-foreground">{announcements[0].content}</p></CardContent></Card>}</div>
    </div>
  </div>;
}

function Meter({ label, value, max, color }: { label: string; value: number; max: number; color: string }) { return <div><div className="mb-1.5 flex justify-between text-[10px] uppercase tracking-wider text-muted-foreground"><span>{label}</span><span className="font-mono">{number(value)} / {number(max)}</span></div><Progress value={percent(value, max)} indicatorClassName={color} className="h-1.5 bg-background/70" /></div>; }
function ValueTile({ label, value, icon: Icon, tone }: { label: string; value: string; icon: React.ElementType; tone: string }) { return <div className="rounded-xl border border-border/70 bg-background/50 p-4"><div className="mb-2 flex items-center gap-2"><Icon size={14} className={tone} /><span className="section-label !text-[9px]">{label}</span></div><p className="font-mono text-lg font-semibold">{value}</p></div>; }
function EmptyState({ icon: Icon, label, detail }: { icon: React.ElementType; label: string; detail: string }) { return <div className="flex flex-col items-center justify-center py-12 text-center"><Icon size={24} className="mb-3 text-muted-foreground/50" /><p className="text-sm font-medium">{label}</p><p className="mt-1 text-xs text-muted-foreground">{detail}</p></div>; }
function DashboardSkeleton() { return <div className="animate-pulse space-y-6"><div className="h-20 w-2/3 rounded-xl bg-muted/50" /><div className="h-56 rounded-2xl bg-muted/50" /><div className="grid gap-4 sm:grid-cols-4">{[1,2,3,4].map((value) => <div key={value} className="h-28 rounded-xl bg-muted/50" />)}</div></div>; }
function ErrorState() { return <Card className="mx-auto max-w-xl"><CardContent className="p-10 text-center"><p className="section-label mb-3 text-primary">Connection interrupted</p><h1 className="text-2xl font-semibold">The realm could not be reached</h1><p className="mt-2 text-sm text-muted-foreground">Check that the API deployment and database are available, then refresh the page.</p><Button className="mt-6" onClick={() => window.location.reload()}>Try again</Button></CardContent></Card>; }
