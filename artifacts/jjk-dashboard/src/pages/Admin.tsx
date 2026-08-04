import React, { useState } from 'react';
import { useGetMe, useAdminListUsers, useGetAdminAnalytics } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Badge } from '@/components/ui/core';
import { ShieldAlert, Users, TrendingUp, AlertTriangle } from 'lucide-react';
import { useLocation } from 'wouter';

export default function Admin() {
  const { data: me, isLoading: meLoading } = useGetMe();
  const [, setLocation] = useLocation();
  const [tab, setTab] = useState<'users' | 'analytics'>('analytics');
  
  const { data: analytics, isLoading: analyticsLoading } = useGetAdminAnalytics({ query: { enabled: !!me?.is_admin } });
  const { data: usersData, isLoading: usersLoading } = useAdminListUsers({ limit: 20 }, { query: { enabled: !!me?.is_admin && tab === 'users' } });

  React.useEffect(() => {
    if (!meLoading && me && !me.is_admin) {
      setLocation('/dashboard');
    }
  }, [me, meLoading, setLocation]);

  if (meLoading || !me?.is_admin) return null;

  return (
    <div className="space-y-8 pb-12">
      <div className="flex items-center gap-4 border-b border-red-500/20 pb-6 mb-8">
        <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center text-red-500">
          <ShieldAlert size={24} />
        </div>
        <div>
          <h1 className="text-3xl font-display font-bold text-red-500">Admin Control</h1>
          <p className="text-muted-foreground text-sm">System oversight and moderation tools.</p>
        </div>
      </div>

      <div className="flex gap-2 mb-8">
        <button onClick={() => setTab('analytics')} className={`px-4 py-2 rounded text-sm font-bold ${tab === 'analytics' ? 'bg-white/10 text-white' : 'text-muted-foreground hover:bg-white/5'}`}>Analytics</button>
        <button onClick={() => setTab('users')} className={`px-4 py-2 rounded text-sm font-bold ${tab === 'users' ? 'bg-white/10 text-white' : 'text-muted-foreground hover:bg-white/5'}`}>Users</button>
      </div>

      {tab === 'analytics' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground tracking-widest flex items-center gap-2"><Users size={14}/> TOTAL PLAYERS</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-mono font-bold text-white">{analytics?.total_players || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground tracking-widest flex items-center gap-2"><TrendingUp size={14}/> ACTIVE TODAY</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-mono font-bold text-white">{analytics?.active_today || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground tracking-widest">TOTAL BATTLES</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-mono font-bold text-white">{analytics?.total_battles || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs text-muted-foreground tracking-widest text-yellow-500">ECONOMY YEN</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-mono font-bold text-yellow-400">¥{analytics?.total_yen_in_circulation?.toLocaleString() || 0}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === 'users' && (
        <Card>
          <div className="p-4 border-b border-white/5 text-xs font-mono text-muted-foreground uppercase tracking-widest grid grid-cols-12 gap-4">
            <div className="col-span-1">ID</div>
            <div className="col-span-3">Name</div>
            <div className="col-span-2">Rank</div>
            <div className="col-span-2">Level</div>
            <div className="col-span-3 text-right">Yen</div>
            <div className="col-span-1"></div>
          </div>
          <div className="p-4 flex flex-col gap-2">
            {usersLoading ? <div className="text-center py-8 text-muted-foreground">Loading...</div> : usersData?.users.map(u => (
              <div key={u.user_id} className="grid grid-cols-12 gap-4 p-3 rounded-lg hover:bg-white/5 items-center border border-white/5">
                <div className="col-span-1 font-mono text-xs">{u.user_id}</div>
                <div className="col-span-3 font-bold text-sm truncate">{u.display_name}</div>
                <div className="col-span-2 text-xs">{u.rank}</div>
                <div className="col-span-2 font-mono text-primary">{u.level}</div>
                <div className="col-span-3 text-right font-mono text-yellow-400">¥{u.yen.toLocaleString()}</div>
                <div className="col-span-1 text-right">
                  {u.is_banned && <AlertTriangle size={16} className="text-red-500 inline" />}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}