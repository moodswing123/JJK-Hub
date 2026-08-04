import React from 'react';
import { useGetDashboardSummary } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Progress, Badge, Button } from '@/components/ui/core';
import { motion } from 'framer-motion';
import { Link } from 'wouter';
import { Swords, Shield, Zap, TrendingUp, ChevronRight, Activity, Bell } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export default function Dashboard() {
  const { data: summary, isLoading } = useGetDashboardSummary();

  if (isLoading || !summary) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-40 glass-card rounded-xl"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-64 glass-card rounded-xl"></div>
          <div className="h-64 glass-card rounded-xl col-span-2"></div>
        </div>
      </div>
    );
  }

  const { player, online_count, recent_activity, announcements, daily_status } = summary;
  const xpPercent = Math.min(100, (player.xp / player.xp_needed) * 100);
  const hpPercent = Math.min(100, (player.hp / player.max_hp) * 100);
  const cePercent = Math.min(100, (player.cursed_energy / player.max_cursed_energy) * 100);

  return (
    <div className="space-y-8 pb-12">
      {/* Header Profile Summary */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card rounded-2xl p-6 md:p-8 relative overflow-hidden"
      >
        <div className="absolute top-0 right-0 p-4 text-xs font-mono text-muted-foreground flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          {online_count} ONLINE
        </div>
        
        <div className="flex flex-col md:flex-row gap-6 md:items-center relative z-10">
          <div className="w-24 h-24 md:w-32 md:h-32 rounded-xl overflow-hidden border-2 border-primary/30 shadow-[0_0_30px_rgba(255,0,0,0.2)] shrink-0">
            {player.avatar_url ? (
              <img src={player.avatar_url} alt={player.display_name} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-primary/20 flex items-center justify-center text-4xl font-bold text-primary">
                {player.display_name.charAt(0)}
              </div>
            )}
          </div>
          
          <div className="flex-1 space-y-4">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-3xl md:text-4xl font-display font-bold text-white">{player.display_name}</h1>
                <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 px-3 py-1">
                  LVL {player.level}
                </Badge>
              </div>
              <div className="text-muted-foreground font-mono text-sm tracking-widest">{player.rank}</div>
            </div>
            
            <div className="space-y-3 max-w-xl">
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-green-400">HP {player.hp}/{player.max_hp}</span>
                </div>
                <Progress value={hpPercent} indicatorClassName="bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]" className="h-1.5 bg-green-950/50" />
              </div>
              
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-blue-400">CE {player.cursed_energy}/{player.max_cursed_energy}</span>
                </div>
                <Progress value={cePercent} indicatorClassName="bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" className="h-1.5 bg-blue-950/50" />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-primary">XP {player.xp}/{player.xp_needed}</span>
                </div>
                <Progress value={xpPercent} indicatorClassName="bg-primary shadow-[0_0_10px_rgba(255,0,0,0.5)]" className="h-1.5 bg-primary/20" />
              </div>
            </div>
          </div>
          
          <div className="flex flex-row md:flex-col gap-4 shrink-0 mt-4 md:mt-0">
            <div className="bg-black/40 border border-white/5 rounded-lg p-4 text-center min-w-[120px]">
              <div className="text-xs text-muted-foreground font-mono mb-1">YEN BALANCE</div>
              <div className="text-xl font-bold font-mono text-yellow-400 text-glow">¥{player.yen.toLocaleString()}</div>
            </div>
            <div className="bg-black/40 border border-white/5 rounded-lg p-4 text-center min-w-[120px]">
              <div className="text-xs text-muted-foreground font-mono mb-1">WIN RATE</div>
              <div className="text-xl font-bold font-mono text-white">{(player.win_rate * 100).toFixed(1)}%</div>
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {/* Left Column */}
        <div className="space-y-8">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.1 }}>
            <Card>
              <CardHeader className="pb-3 border-b border-white/5">
                <CardTitle className="text-sm tracking-widest text-muted-foreground flex items-center gap-2">
                  <Activity size={16} />
                  COMBAT STATS
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 text-muted-foreground">
                      <div className="w-8 h-8 rounded bg-red-500/10 flex items-center justify-center text-red-500">
                        <Swords size={18} />
                      </div>
                      <span className="font-mono text-sm">ATTACK</span>
                    </div>
                    <span className="font-mono font-bold">{player.attack.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 text-muted-foreground">
                      <div className="w-8 h-8 rounded bg-blue-500/10 flex items-center justify-center text-blue-500">
                        <Shield size={18} />
                      </div>
                      <span className="font-mono text-sm">DEFENSE</span>
                    </div>
                    <span className="font-mono font-bold">{player.defense.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 text-muted-foreground">
                      <div className="w-8 h-8 rounded bg-yellow-500/10 flex items-center justify-center text-yellow-500">
                        <Zap size={18} />
                      </div>
                      <span className="font-mono text-sm">SPEED</span>
                    </div>
                    <span className="font-mono font-bold">{player.speed.toLocaleString()}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <Card className="bg-gradient-to-br from-primary/10 to-transparent border-primary/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm tracking-widest flex items-center gap-2">
                  <TrendingUp size={16} className="text-primary" />
                  DAILY REWARDS
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center text-center space-y-4">
                  <div className="text-4xl font-display font-bold text-primary">
                    {daily_status?.streak || 0} <span className="text-xl text-muted-foreground">DAYS</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {daily_status?.can_claim ? 'Your daily reward is ready!' : 'Already claimed today.'}
                  </p>
                  <Link href="/daily" className="w-full">
                    <Button variant={daily_status?.can_claim ? 'default' : 'secondary'} className="w-full">
                      {daily_status?.can_claim ? 'CLAIM REWARD' : 'VIEW MISSIONS'}
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Middle & Right Column */}
        <div className="md:col-span-2 space-y-8">
          
          {announcements.length > 0 && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
              <Card className="border-secondary/30 bg-secondary/5">
                <CardHeader className="pb-4">
                  <CardTitle className="text-sm tracking-widest flex items-center gap-2 text-secondary-foreground">
                    <Bell size={16} />
                    ANNOUNCEMENTS
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {announcements.slice(0,2).map(ann => (
                    <div key={ann.id} className="p-4 rounded-lg bg-black/40 border border-white/5">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-bold text-lg">{ann.title}</h4>
                        <span className="text-xs text-muted-foreground">{formatDistanceToNow(new Date(ann.created_at))} ago</span>
                      </div>
                      <p className="text-sm text-muted-foreground leading-relaxed">{ann.content}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </motion.div>
          )}

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between pb-4 border-b border-white/5">
                <CardTitle className="text-sm tracking-widest">RECENT ACTIVITY</CardTitle>
                <Link href="/profile">
                  <Button variant="ghost" size="sm" className="text-xs h-8 text-muted-foreground">View All <ChevronRight size={14} /></Button>
                </Link>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="space-y-4">
                  {recent_activity.length > 0 ? recent_activity.map((entry) => (
                    <div key={entry.id} className="flex gap-4 items-start pb-4 border-b border-white/5 last:border-0 last:pb-0">
                      <div className="w-2 h-2 rounded-full bg-primary mt-2 shadow-[0_0_8px_rgba(255,0,0,0.8)]"></div>
                      <div className="flex-1">
                        <p className="text-sm text-gray-300">{entry.message}</p>
                        <span className="text-xs text-muted-foreground font-mono mt-1 block">
                          {formatDistanceToNow(new Date(entry.created_at))} ago
                        </span>
                      </div>
                    </div>
                  )) : (
                    <div className="text-center py-8 text-muted-foreground text-sm">
                      No recent activity. Get out there and exorcise some curses!
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
