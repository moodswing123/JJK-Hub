import React, { useState } from 'react';
import { useGetCasinoStats, usePlayCoinFlip, useGetMyPlayer } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Button, Input } from '@/components/ui/core';
import { motion, AnimatePresence } from 'framer-motion';
import { Coins, Dice5, RotateCcw, AlertTriangle, TrendingUp, History } from 'lucide-react';
import { Badge } from '@/components/ui/core';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMyPlayerQueryKey, getGetCasinoStatsQueryKey } from '@workspace/api-client-react';

const GAMES = [
  { id: 'coinflip', name: 'Coin Flip', icon: Coins, color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/30' },
  { id: 'dice', name: 'Dice Roll', icon: Dice5, color: 'text-purple-400', bg: 'bg-purple-400/10', border: 'border-purple-400/30' },
  { id: 'roulette', name: 'Roulette', icon: RotateCcw, color: 'text-red-400', bg: 'bg-red-400/10', border: 'border-red-400/30' },
];

export default function Casino() {
  const { data: stats } = useGetCasinoStats();
  const { data: player } = useGetMyPlayer({ query: { queryKey: getGetMyPlayerQueryKey(), retry: false } });
  const [selectedGame, setSelectedGame] = useState('coinflip');
  const [bet, setBet] = useState('');
  const [choice, setChoice] = useState('heads');
  const [result, setResult] = useState<any>(null);
  const [isFlipping, setIsFlipping] = useState(false);

  const coinFlipMutation = usePlayCoinFlip();
  const queryClient = useQueryClient();

  const handlePlayCoinFlip = async () => {
    if (!bet || isNaN(Number(bet)) || Number(bet) <= 0) return;
    
    setIsFlipping(true);
    setResult(null);
    
    // Fake delay for animation
    setTimeout(async () => {
      try {
        const res = await coinFlipMutation.mutateAsync({ data: { bet: Number(bet), choice } });
        setResult(res);
        queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetCasinoStatsQueryKey() });
      } catch(e) {
        console.error(e);
      } finally {
        setIsFlipping(false);
      }
    }, 1500);
  };

  return (
    <div className="space-y-8 pb-12 max-w-6xl mx-auto">
      <div className="text-center mb-10 relative">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-yellow-500/10 rounded-full blur-[80px] pointer-events-none"></div>
        <h1 className="text-4xl md:text-5xl font-display font-black mb-4 uppercase tracking-widest text-glow-accent relative z-10">Cursed Casino</h1>
        <p className="text-muted-foreground max-w-lg mx-auto relative z-10">
          Risk your Yen. Test your luck. Will you leave rich or cursed?
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Game Selector Sidebar */}
        <div className="space-y-4">
          <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest mb-4">Select Game</div>
          {GAMES.map(game => {
            const Icon = game.icon;
            const isActive = selectedGame === game.id;
            return (
              <motion.button
                key={game.id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => { setSelectedGame(game.id); setResult(null); }}
                className={`w-full p-4 rounded-xl flex items-center gap-4 transition-all duration-300 border-2 text-left ${
                  isActive 
                    ? `${game.bg} ${game.border} shadow-[0_0_20px_rgba(0,0,0,0.5)]` 
                    : 'bg-black/40 border-white/5 hover:border-white/20'
                }`}
              >
                <div className={`p-3 rounded-lg ${isActive ? 'bg-black/50' : 'bg-white/5'} ${game.color}`}>
                  <Icon size={24} />
                </div>
                <div>
                  <div className={`font-display font-bold text-lg ${isActive ? 'text-white' : 'text-muted-foreground'}`}>{game.name}</div>
                  <div className="text-xs font-mono text-muted-foreground opacity-60">{isActive ? 'Currently Playing' : 'Click to Switch'}</div>
                </div>
              </motion.button>
            )
          })}

          {stats && (
            <Card className="mt-8 bg-black/60 border-white/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-mono tracking-widest text-muted-foreground flex items-center gap-2">
                  <TrendingUp size={16} /> YOUR STATS
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Win Rate</span>
                    <span className="font-mono text-white">{(stats.win_rate! * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Total Won</span>
                    <span className="font-mono text-green-400">+¥{stats.total_won.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Biggest Payout</span>
                    <span className="font-mono text-yellow-400">¥{stats.biggest_win.toLocaleString()}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Game Arena */}
        <div className="lg:col-span-2">
          <Card className="h-[600px] border-white/10 relative overflow-hidden flex flex-col bg-gradient-to-br from-black to-zinc-900">
            {/* Arena Header */}
            <div className="p-4 border-b border-white/5 flex justify-between items-center bg-black/50 relative z-10">
              <div className="font-mono font-bold flex items-center gap-2 text-yellow-400">
                <Coins size={16} /> ¥{player?.yen.toLocaleString() || 0}
              </div>
              <Badge variant="outline" className="text-xs tracking-widest font-mono border-red-500/30 text-red-400">
                HOUSE EDGE: 2.5%
              </Badge>
            </div>

            {/* Game Canvas */}
            <div className="flex-1 flex flex-col items-center justify-center p-8 relative z-10">
              {selectedGame === 'coinflip' ? (
                <>
                  <div className="mb-12 h-32 w-32 relative">
                    <AnimatePresence mode="wait">
                      {isFlipping ? (
                        <motion.div
                          key="flipping"
                          animate={{ rotateY: 1080 }}
                          transition={{ duration: 1.5, ease: "linear" }}
                          className="w-full h-full rounded-full bg-gradient-to-br from-yellow-300 to-yellow-600 shadow-[0_0_50px_rgba(250,204,21,0.5)] flex items-center justify-center border-4 border-yellow-200"
                        >
                          <span className="font-display font-black text-4xl text-yellow-900">?</span>
                        </motion.div>
                      ) : result ? (
                        <motion.div
                          key="result"
                          initial={{ scale: 0, rotateY: 180 }}
                          animate={{ scale: 1, rotateY: 0 }}
                          className={`w-full h-full rounded-full flex items-center justify-center border-4 shadow-[0_0_50px_rgba(250,204,21,0.3)] ${
                            result.won 
                              ? 'bg-gradient-to-br from-yellow-300 to-yellow-600 border-yellow-200 text-yellow-900' 
                              : 'bg-gradient-to-br from-gray-700 to-gray-900 border-gray-500 text-gray-400'
                          }`}
                        >
                          <span className="font-display font-black text-3xl uppercase">
                            {result.details?.landed_on || 'RESULT'}
                          </span>
                        </motion.div>
                      ) : (
                        <motion.div
                          key="idle"
                          animate={{ y: [0, -10, 0] }}
                          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                          className="w-full h-full rounded-full bg-gradient-to-br from-yellow-400/20 to-yellow-600/20 border-2 border-yellow-500/30 flex items-center justify-center"
                        >
                          <Coins size={48} className="text-yellow-500/50" />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {result && !isFlipping && (
                    <motion.div
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`text-center mb-8 px-8 py-4 rounded-xl border ${
                        result.won ? 'bg-green-500/10 border-green-500/30 text-green-400' : 'bg-red-500/10 border-red-500/30 text-red-400'
                      }`}
                    >
                      <div className="font-display font-bold text-2xl mb-1">{result.outcome_text}</div>
                      <div className="font-mono text-sm">
                        {result.won ? `+¥${result.payout.toLocaleString()}` : `-¥${Number(bet).toLocaleString()}`}
                      </div>
                    </motion.div>
                  )}
                </>
              ) : (
                <div className="text-center text-muted-foreground flex flex-col items-center">
                  <AlertTriangle size={48} className="mb-4 opacity-20" />
                  <h3 className="font-display text-xl">Game Under Construction</h3>
                  <p className="text-sm mt-2 max-w-xs">Sukuna destroyed this part of the casino. We are rebuilding it.</p>
                </div>
              )}
            </div>

            {/* Controls (Coin Flip specific for now) */}
            {selectedGame === 'coinflip' && (
              <div className="bg-black/60 p-6 border-t border-white/5 relative z-10">
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <button
                    disabled={isFlipping}
                    onClick={() => setChoice('heads')}
                    className={`py-3 rounded-lg font-bold tracking-widest transition-colors ${
                      choice === 'heads' ? 'bg-yellow-500 text-black' : 'bg-white/5 text-muted-foreground hover:bg-white/10'
                    }`}
                  >
                    HEADS
                  </button>
                  <button
                    disabled={isFlipping}
                    onClick={() => setChoice('tails')}
                    className={`py-3 rounded-lg font-bold tracking-widest transition-colors ${
                      choice === 'tails' ? 'bg-yellow-500 text-black' : 'bg-white/5 text-muted-foreground hover:bg-white/10'
                    }`}
                  >
                    TAILS
                  </button>
                </div>
                
                <div className="flex gap-4">
                  <div className="relative flex-1">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-yellow-500 font-bold">¥</span>
                    <Input
                      type="number"
                      placeholder="Bet Amount"
                      value={bet}
                      onChange={(e) => setBet(e.target.value)}
                      disabled={isFlipping}
                      className="pl-10 text-lg h-14 bg-black/50 border-white/10 focus-visible:border-yellow-500/50 focus-visible:ring-yellow-500/20"
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                      <button onClick={() => setBet(String(Math.max(1, Math.floor(Number(bet || 0) / 2))))} className="px-2 py-1 bg-white/10 rounded text-xs hover:bg-white/20">1/2</button>
                      <button onClick={() => setBet(String(Number(bet || 0) * 2))} className="px-2 py-1 bg-white/10 rounded text-xs hover:bg-white/20">2x</button>
                      <button onClick={() => setBet(String(player?.yen || 0))} className="px-2 py-1 bg-white/10 rounded text-xs hover:bg-white/20">MAX</button>
                    </div>
                  </div>
                  <Button 
                    onClick={handlePlayCoinFlip} 
                    disabled={isFlipping || !bet || Number(bet) <= 0 || Number(bet) > (player?.yen || 0)}
                    className="h-14 px-8 bg-primary hover:bg-primary/90 text-lg font-bold box-glow"
                  >
                    {isFlipping ? 'FLIPPING...' : 'PLACE BET'}
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
