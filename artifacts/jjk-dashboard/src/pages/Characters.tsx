import React from 'react';
import { useListCharacters, useGetMyPlayer, useEquipCharacter } from '@workspace/api-client-react';
import { Card, Button, Badge } from '@/components/ui/core';
import { motion, AnimatePresence } from 'framer-motion';
import { Lock, Zap, Shield, Swords, Info } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMyPlayerQueryKey } from '@workspace/api-client-react';

const GRADE_COLORS: Record<string, string> = {
  'Grade 4': 'text-gray-400 border-gray-400',
  'Grade 3': 'text-blue-400 border-blue-400',
  'Grade 2': 'text-green-400 border-green-400',
  'Grade 1': 'text-purple-400 border-purple-400',
  'Special Grade': 'text-red-500 border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)]',
};

const GRADE_BG: Record<string, string> = {
  'Grade 4': 'bg-gray-900/50',
  'Grade 3': 'bg-blue-900/20',
  'Grade 2': 'bg-green-900/20',
  'Grade 1': 'bg-purple-900/20',
  'Special Grade': 'bg-red-900/20',
};

export default function Characters() {
  const { data: characters, isLoading: charsLoading } = useListCharacters();
  const { data: player, isLoading: playerLoading } = useGetMyPlayer({ query: { retry: false } });
  const equipMutation = useEquipCharacter();
  const queryClient = useQueryClient();
  const [selectedChar, setSelectedChar] = React.useState<number | null>(null);

  if (charsLoading || playerLoading || !characters || !player) {
    return <div className="animate-pulse space-y-8">
      <div className="h-10 w-48 bg-white/10 rounded"></div>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {[...Array(8)].map((_, i) => <div key={i} className="h-80 bg-white/5 rounded-xl"></div>)}
      </div>
    </div>;
  }

  const handleEquip = async (charId: number) => {
    try {
      await equipMutation.mutateAsync({ data: { character_id: charId } });
      queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
    } catch (e) {
      console.error(e);
    }
  };

  const activeChar = characters.find(c => c.id === selectedChar);

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h1 className="text-3xl font-display font-bold mb-2">Character Roster</h1>
        <p className="text-muted-foreground">Unlock and equip characters to use their stats and techniques in battle.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Gallery */}
        <div className="lg:col-span-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6">
          {characters.map((char, i) => {
            const isEquipped = player.character_id === char.id;
            const isSelected = selectedChar === char.id;
            // In a real app we'd check if owned. For now, assume all are viewable, some owned.
            // We'll simulate ownership if they have the character equipped or we can just let them equip any.
            // The API schema doesn't show character ownership array, it might be just unlocked by level/yen.
            
            return (
              <motion.div
                key={char.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                onClick={() => setSelectedChar(char.id)}
                className={`relative rounded-xl overflow-hidden cursor-pointer transition-all duration-300 border-2 ${
                  isSelected ? 'border-primary shadow-[0_0_20px_rgba(255,0,0,0.3)] scale-105 z-10' : 
                  isEquipped ? 'border-white/40' : 'border-white/5 hover:border-white/20'
                }`}
              >
                {/* Character Card Background - would be an image normally */}
                <div className={`h-64 ${GRADE_BG[char.grade] || 'bg-black'} relative p-4 flex flex-col justify-end`}>
                  {char.image_url ? (
                    <img src={char.image_url} alt={char.name} className="absolute inset-0 w-full h-full object-cover mix-blend-overlay opacity-50" />
                  ) : (
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/50 to-transparent" />
                  )}
                  
                  {isEquipped && (
                    <div className="absolute top-3 right-3 bg-primary text-primary-foreground text-[10px] font-bold px-2 py-1 rounded">
                      EQUIPPED
                    </div>
                  )}

                  <div className="relative z-10">
                    <h3 className="font-display font-bold text-xl mb-1">{char.name}</h3>
                    <Badge variant="outline" className={`${GRADE_COLORS[char.grade]} bg-black/50 px-2 py-0.5 text-[10px]`}>
                      {char.grade}
                    </Badge>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Detail Panel */}
        <div className="lg:col-span-1">
          <div className="sticky top-24">
            <AnimatePresence mode="wait">
              {activeChar ? (
                <motion.div
                  key={activeChar.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                >
                  <Card className="border-white/10 overflow-hidden">
                    <div className={`h-32 ${GRADE_BG[activeChar.grade]} relative`}>
                       {activeChar.image_url && <img src={activeChar.image_url} className="w-full h-full object-cover opacity-30" />}
                       <div className="absolute inset-0 bg-gradient-to-t from-card to-transparent" />
                    </div>
                    
                    <div className="p-6 -mt-10 relative z-10">
                      <div className="mb-6 text-center">
                        <h2 className="text-2xl font-display font-bold mb-1">{activeChar.name}</h2>
                        <span className={`text-xs font-mono border px-2 py-1 rounded-full ${GRADE_COLORS[activeChar.grade]}`}>
                          {activeChar.grade}
                        </span>
                      </div>

                      {activeChar.quote && (
                        <p className="text-sm italic text-muted-foreground text-center mb-6">"{activeChar.quote}"</p>
                      )}

                      <div className="space-y-4 mb-6">
                        <div className="flex justify-between items-center text-sm border-b border-white/5 pb-2">
                          <span className="text-muted-foreground flex items-center gap-2"><Swords size={14}/> Attack</span>
                          <span className="font-mono font-bold">{activeChar.attack}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm border-b border-white/5 pb-2">
                          <span className="text-muted-foreground flex items-center gap-2"><Shield size={14}/> Defense</span>
                          <span className="font-mono font-bold">{activeChar.defense}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm border-b border-white/5 pb-2">
                          <span className="text-muted-foreground flex items-center gap-2"><Zap size={14}/> Speed</span>
                          <span className="font-mono font-bold">{activeChar.speed}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm border-b border-white/5 pb-2">
                          <span className="text-muted-foreground flex items-center gap-2">HP</span>
                          <span className="font-mono font-bold text-green-400">{activeChar.max_hp}</span>
                        </div>
                        <div className="flex justify-between items-center text-sm border-b border-white/5 pb-2">
                          <span className="text-muted-foreground flex items-center gap-2">CE</span>
                          <span className="font-mono font-bold text-blue-400">{activeChar.max_ce}</span>
                        </div>
                      </div>

                      <div className="mb-6">
                        <h4 className="text-xs tracking-widest text-muted-foreground mb-2">TECHNIQUE</h4>
                        <div className="bg-white/5 p-3 rounded-md text-sm text-primary font-medium">
                          {activeChar.technique}
                        </div>
                      </div>

                      <Button 
                        className="w-full" 
                        disabled={player.character_id === activeChar.id || equipMutation.isPending}
                        onClick={() => handleEquip(activeChar.id)}
                      >
                        {equipMutation.isPending ? 'EQUIPPING...' : player.character_id === activeChar.id ? 'EQUIPPED' : 'EQUIP CHARACTER'}
                      </Button>
                    </div>
                  </Card>
                </motion.div>
              ) : (
                <div className="h-[500px] glass-card flex flex-col items-center justify-center text-muted-foreground text-center p-8 border-dashed border-2 border-white/10">
                  <Info size={48} className="mb-4 opacity-20" />
                  <p>Select a character from the roster to view details and equip.</p>
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}