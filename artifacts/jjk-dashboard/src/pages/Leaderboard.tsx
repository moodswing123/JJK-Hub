import React, { useState } from 'react';
import { useGetLevelLeaderboard, useGetWealthLeaderboard, useGetPvpLeaderboard } from '@workspace/api-client-react';
import { Card, CardContent } from '@/components/ui/core';
import { motion, AnimatePresence } from 'framer-motion';
import { Trophy, TrendingUp, Swords, Medal } from 'lucide-react';

export default function Leaderboard() {
  const [tab, setTab] = useState<'level' | 'wealth' | 'pvp'>('level');
  
  const { data: levelData, isLoading: levelLoading } = useGetLevelLeaderboard({ limit: 50 });
  const { data: wealthData, isLoading: wealthLoading } = useGetWealthLeaderboard({ limit: 50 });
  const { data: pvpData, isLoading: pvpLoading } = useGetPvpLeaderboard({ limit: 50 });

  const currentData = tab === 'level' ? levelData : tab === 'wealth' ? wealthData : pvpData;
  const isLoading = tab === 'level' ? levelLoading : tab === 'wealth' ? wealthLoading : pvpLoading;

  const getRankStyle = (index: number) => {
    if (index === 0) return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30 text-glow shadow-[0_0_15px_rgba(250,204,21,0.2)]';
    if (index === 1) return 'text-gray-300 bg-gray-300/10 border-gray-300/30';
    if (index === 2) return 'text-amber-600 bg-amber-600/10 border-amber-600/30';
    return 'text-muted-foreground bg-black/40 border-white/5';
  };

  return (
    <div className="space-y-8 pb-12 max-w-4xl mx-auto">
      <div className="text-center mb-10">
        <h1 className="text-4xl font-display font-black mb-4 uppercase tracking-widest text-glow">Global Rankings</h1>
        <p className="text-muted-foreground max-w-lg mx-auto">
          The strongest sorcerers, the wealthiest curse users, and the most dominant fighters.
        </p>
      </div>

      <div className="flex justify-center mb-8">
        <div className="glass p-1 rounded-xl inline-flex gap-1 border border-white/10">
          <button
            onClick={() => setTab('level')}
            className={`px-6 py-2.5 rounded-lg flex items-center gap-2 text-sm font-bold tracking-wide transition-all ${tab === 'level' ? 'bg-primary text-white shadow-lg' : 'text-muted-foreground hover:text-white hover:bg-white/5'}`}
          >
            <TrendingUp size={16} /> HIGHEST LEVEL
          </button>
          <button
            onClick={() => setTab('wealth')}
            className={`px-6 py-2.5 rounded-lg flex items-center gap-2 text-sm font-bold tracking-wide transition-all ${tab === 'wealth' ? 'bg-secondary text-white shadow-lg' : 'text-muted-foreground hover:text-white hover:bg-white/5'}`}
          >
            <Trophy size={16} /> MOST WEALTH
          </button>
          <button
            onClick={() => setTab('pvp')}
            className={`px-6 py-2.5 rounded-lg flex items-center gap-2 text-sm font-bold tracking-wide transition-all ${tab === 'pvp' ? 'bg-accent text-white shadow-lg' : 'text-muted-foreground hover:text-white hover:bg-white/5'}`}
          >
            <Swords size={16} /> DOMINANCE
          </button>
        </div>
      </div>

      <div className="glass-card rounded-2xl overflow-hidden border border-white/10">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-4 p-4 border-b border-white/10 bg-white/[0.02] text-xs font-mono text-muted-foreground uppercase tracking-widest">
          <div className="col-span-2 md:col-span-1 text-center">Rank</div>
          <div className="col-span-6 md:col-span-5">Sorcerer</div>
          <div className="col-span-4 md:col-span-3 text-right md:text-left">Grade</div>
          <div className="hidden md:block md:col-span-3 text-right">
            {tab === 'level' ? 'Level & XP' : tab === 'wealth' ? 'Yen Balance' : 'Win Rate'}
          </div>
        </div>

        {/* Table Body */}
        <div className="min-h-[500px]">
          {isLoading ? (
            <div className="p-4 space-y-4">
              {[...Array(10)].map((_, i) => (
                <div key={i} className="h-16 bg-white/5 animate-pulse rounded-xl"></div>
              ))}
            </div>
          ) : (
            <div className="p-4 space-y-3">
              <AnimatePresence mode="popLayout">
                {currentData?.map((entry, index) => (
                  <motion.div
                    key={entry.user_id}
                    layout
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ delay: index * 0.05, type: 'spring', stiffness: 300, damping: 30 }}
                  >
                    <div className="grid grid-cols-12 gap-4 items-center p-3 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 group">
                      
                      {/* Rank Badge */}
                      <div className="col-span-2 md:col-span-1 flex justify-center">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center font-display font-bold border ${getRankStyle(index)}`}>
                          {index < 3 ? <Medal size={16} className={index === 0 ? 'fill-yellow-400' : index === 1 ? 'fill-gray-300' : 'fill-amber-600'} /> : index + 1}
                        </div>
                      </div>
                      
                      {/* Player Info */}
                      <div className="col-span-6 md:col-span-5 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-black/50 shrink-0 border border-white/10 group-hover:border-primary/50 transition-colors">
                          {entry.avatar_url ? (
                            <img src={entry.avatar_url} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-primary font-bold bg-primary/10">
                              {entry.display_name.charAt(0)}
                            </div>
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-white truncate">{entry.display_name}</div>
                          {entry.username && <div className="text-xs text-muted-foreground truncate">@{entry.username}</div>}
                        </div>
                      </div>

                      {/* Grade */}
                      <div className="col-span-4 md:col-span-3 text-right md:text-left flex items-center md:justify-start justify-end">
                        <span className="text-xs font-mono px-2 py-1 rounded bg-black/50 border border-white/5">
                          {entry.rank || 'Unranked'}
                        </span>
                      </div>

                      {/* Stat */}
                      <div className="hidden md:block md:col-span-3 text-right">
                        {tab === 'level' && (
                          <div className="font-mono text-primary font-bold text-glow text-lg">
                            LVL {entry.level}
                          </div>
                        )}
                        {tab === 'wealth' && (
                          <div className="font-mono text-yellow-400 font-bold text-glow text-lg">
                            ¥{entry.yen.toLocaleString()}
                          </div>
                        )}
                        {tab === 'pvp' && (
                          <div className="flex flex-col items-end">
                            <div className="font-mono text-white font-bold text-lg">
                              {(entry.win_rate * 100).toFixed(1)}%
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {entry.wins} Wins
                            </div>
                          </div>
                        )}
                      </div>

                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}