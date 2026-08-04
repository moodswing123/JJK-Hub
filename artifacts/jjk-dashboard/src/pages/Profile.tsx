import React, { useState } from 'react';
import { useGetMyPlayer, useUpdateMyProfile } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Button, Input } from '@/components/ui/core';
import { motion } from 'framer-motion';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMyPlayerQueryKey } from '@workspace/api-client-react';
import { Camera, Edit2, Hexagon, Shield, Zap } from 'lucide-react';

export default function Profile() {
  const { data: player, isLoading } = useGetMyPlayer();
  const updateMutation = useUpdateMyProfile();
  const queryClient = useQueryClient();
  
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    bio: '',
    avatar_url: '',
    banner_url: ''
  });

  React.useEffect(() => {
    if (player) {
      setFormData({
        bio: player.bio || '',
        avatar_url: player.avatar_url || '',
        banner_url: player.banner_url || ''
      });
    }
  }, [player]);

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({ data: formData });
      queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
      setIsEditing(false);
    } catch(e) {}
  };

  if (isLoading || !player) {
    return <div className="animate-pulse space-y-8">
      <div className="h-64 bg-white/5 rounded-xl w-full"></div>
    </div>;
  }

  return (
    <div className="space-y-8 pb-12 max-w-4xl mx-auto">
      {/* Banner & Avatar */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative rounded-2xl overflow-hidden glass-card border-white/10">
        <div className="h-48 md:h-64 w-full bg-gradient-to-r from-primary/20 to-secondary/20 relative">
          {player.banner_url && (
            <img src={player.banner_url} className="w-full h-full object-cover mix-blend-overlay opacity-50" alt="Banner" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent" />
          
          {isEditing && (
            <div className="absolute top-4 right-4 z-20">
              <Button size="sm" variant="secondary" onClick={() => {
                const url = prompt("Enter banner image URL:", formData.banner_url);
                if (url !== null) setFormData({...formData, banner_url: url});
              }}>
                <Camera size={14} className="mr-2"/> Change Banner
              </Button>
            </div>
          )}
        </div>
        
        <div className="px-8 pb-8 relative -mt-20 flex flex-col md:flex-row gap-6 items-end md:items-start">
          <div className="relative group">
            <div className="w-32 h-32 md:w-40 md:h-40 rounded-2xl overflow-hidden border-4 border-background bg-muted relative z-10 shadow-xl">
              {player.avatar_url ? (
                <img src={player.avatar_url} alt={player.display_name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-4xl font-bold bg-primary/20 text-primary">
                  {player.display_name.charAt(0)}
                </div>
              )}
            </div>
            {isEditing && (
              <button 
                onClick={() => {
                  const url = prompt("Enter avatar image URL:", formData.avatar_url);
                  if (url !== null) setFormData({...formData, avatar_url: url});
                }}
                className="absolute inset-0 z-20 flex items-center justify-center bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl cursor-pointer"
              >
                <Camera className="text-white" />
              </button>
            )}
          </div>
          
          <div className="flex-1 text-center md:text-left mt-4 md:mt-16 w-full">
            <div className="flex flex-col md:flex-row justify-between items-center md:items-end gap-4">
              <div>
                <h1 className="text-3xl font-display font-bold">{player.display_name}</h1>
                <div className="text-muted-foreground font-mono mt-1">{player.rank} • LVL {player.level}</div>
              </div>
              
              {!isEditing ? (
                <Button variant="outline" onClick={() => setIsEditing(true)}>
                  <Edit2 size={16} className="mr-2" /> Edit Profile
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button variant="ghost" onClick={() => setIsEditing(false)}>Cancel</Button>
                  <Button onClick={handleSave} disabled={updateMutation.isPending}>Save Changes</Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2 space-y-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Sorcerer Bio</CardTitle>
            </CardHeader>
            <CardContent>
              {isEditing ? (
                <textarea 
                  className="w-full h-32 bg-black/50 border border-white/10 rounded-md p-3 text-sm focus:outline-none focus:border-primary/50 text-white resize-none"
                  placeholder="Write your backstory..."
                  value={formData.bio}
                  onChange={e => setFormData({...formData, bio: e.target.value})}
                />
              ) : (
                <p className="text-muted-foreground text-sm leading-relaxed whitespace-pre-wrap">
                  {player.bio || "No bio provided. This sorcerer remains a mystery."}
                </p>
              )}
            </CardContent>
          </Card>
          
          {/* Domain Expansion Placeholder */}
          <Card className="border-secondary/30 bg-secondary/5 overflow-hidden relative">
            <div className="absolute right-0 top-0 opacity-10 pointer-events-none">
              <Hexagon size={200} className="text-secondary -mr-10 -mt-10" />
            </div>
            <CardHeader>
              <CardTitle className="text-lg text-secondary-foreground flex items-center gap-2">
                <Hexagon size={18} /> Domain Expansion
              </CardTitle>
            </CardHeader>
            <CardContent>
              {player.domain_name ? (
                <div>
                  <h3 className="font-display text-2xl font-bold mb-2 text-white">{player.domain_name}</h3>
                  <div className="text-sm font-mono text-secondary-foreground">POWER LEVEL: {player.domain_power || 'UNKNOWN'}</div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <p className="text-muted-foreground text-sm mb-4">You have not realized your Domain Expansion yet.</p>
                  <Button variant="secondary" size="sm" disabled>Unlock at Special Grade</Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm text-muted-foreground tracking-widest">RECORD</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between items-center pb-3 border-b border-white/5">
                  <span className="text-muted-foreground">Battles Won</span>
                  <span className="font-mono text-white font-bold">{player.wins}</span>
                </div>
                <div className="flex justify-between items-center pb-3 border-b border-white/5">
                  <span className="text-muted-foreground">Battles Lost</span>
                  <span className="font-mono text-white font-bold">{player.losses}</span>
                </div>
                <div className="flex justify-between items-center pb-3 border-b border-white/5">
                  <span className="text-muted-foreground">Win Rate</span>
                  <span className="font-mono text-primary font-bold">{(player.win_rate * 100).toFixed(1)}%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}