import React from 'react';
import { useGetDailyStatus, useListDailyMissions, useClaimDaily } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Button, Progress, Badge } from '@/components/ui/core';
import { motion } from 'framer-motion';
import { Gift, Zap, Target, CheckCircle2, Coins, Clock } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMyPlayerQueryKey, getGetDailyStatusQueryKey, getListDailyMissionsQueryKey } from '@workspace/api-client-react';

export default function Daily() {
  const { data: status, isLoading: statusLoading } = useGetDailyStatus();
  const { data: missions, isLoading: missionsLoading } = useListDailyMissions();
  const claimMutation = useClaimDaily();
  const queryClient = useQueryClient();

  const handleClaim = async () => {
    try {
      await claimMutation.mutateAsync(undefined);
      queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetDailyStatusQueryKey() });
    } catch(e) {}
  };

  if (statusLoading || missionsLoading) {
    return <div className="animate-pulse space-y-8">
      <div className="h-64 glass-card rounded-xl"></div>
      <div className="h-96 glass-card rounded-xl"></div>
    </div>;
  }

  return (
    <div className="space-y-8 pb-12 max-w-5xl mx-auto">
      
      {/* Daily Login Reward */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card className="relative overflow-hidden border-primary/30">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-transparent pointer-events-none" />
          
          <CardContent className="p-8 md:p-12 text-center relative z-10">
            <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 border-2 border-primary/30 shadow-[0_0_30px_rgba(255,0,0,0.2)] mb-6">
              <Gift size={48} className="text-primary" />
            </div>
            
            <h2 className="text-3xl md:text-4xl font-display font-bold mb-4">Daily Login Reward</h2>
            
            <div className="flex items-center justify-center gap-6 mb-8">
              <div className="text-center">
                <div className="text-sm text-muted-foreground uppercase tracking-widest mb-1">Current Streak</div>
                <div className="text-4xl font-mono font-black text-white">{status?.streak || 0} <span className="text-xl text-primary">🔥</span></div>
              </div>
            </div>
            
            <Button 
              size="lg" 
              className={`h-16 px-12 text-xl font-bold rounded-xl transition-all duration-500 ${
                status?.can_claim 
                  ? 'bg-primary hover:bg-primary/90 text-white shadow-[0_0_40px_rgba(255,0,0,0.5)] hover:scale-105' 
                  : 'bg-white/5 text-muted-foreground border border-white/10'
              }`}
              onClick={handleClaim}
              disabled={!status?.can_claim || claimMutation.isPending}
            >
              {claimMutation.isPending ? (
                'CLAIMING...'
              ) : status?.can_claim ? (
                'CLAIM REWARD'
              ) : (
                <span className="flex items-center gap-2"><CheckCircle2 /> CLAIMED TODAY</span>
              )}
            </Button>
            
            {!status?.can_claim && status?.next_claim_at && (
              <p className="mt-6 text-sm text-muted-foreground font-mono flex items-center justify-center gap-2">
                <Clock size={14} /> Next reward available at 00:00 UTC
              </p>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* Daily Missions */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div className="flex items-center gap-3 mb-6">
          <Target className="text-secondary" />
          <h2 className="text-2xl font-display font-bold">Daily Missions</h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {missions?.map((mission, index) => {
            const isCompleted = mission.completed === 1;
            const progress = Math.min(100, (mission.current_value / mission.target_value) * 100);
            
            return (
              <motion.div
                key={mission.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 * index }}
              >
                <Card className={`h-full ${isCompleted ? 'border-green-500/30 bg-green-950/10' : 'border-white/10'}`}>
                  <CardContent className="p-6">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="font-bold text-lg mb-1">{mission.name}</h3>
                        <p className="text-sm text-muted-foreground">{mission.description}</p>
                      </div>
                      {isCompleted && (
                        <Badge variant="outline" className="bg-green-500/20 text-green-400 border-green-500/30">
                          COMPLETED
                        </Badge>
                      )}
                    </div>
                    
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <div className="flex justify-between text-xs font-mono text-muted-foreground">
                          <span>PROGRESS</span>
                          <span>{mission.current_value} / {mission.target_value}</span>
                        </div>
                        <Progress 
                          value={progress} 
                          indicatorClassName={isCompleted ? 'bg-green-500' : 'bg-secondary'} 
                          className="bg-black/50"
                        />
                      </div>
                      
                      <div className="flex items-center gap-4 pt-4 border-t border-white/5">
                        <div className="text-xs text-muted-foreground uppercase tracking-widest">Rewards</div>
                        <div className="flex items-center gap-2 text-sm font-mono font-bold text-yellow-400">
                          <Coins size={14} /> ¥{mission.reward_yen}
                        </div>
                        <div className="flex items-center gap-2 text-sm font-mono font-bold text-primary">
                          <Zap size={14} /> {mission.reward_xp} XP
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

    </div>
  );
}
