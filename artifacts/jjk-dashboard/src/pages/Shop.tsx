import React, { useState } from 'react';
import { useListShopItems, useListPremiumPacks, usePurchaseShopItem } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Button, Badge } from '@/components/ui/core';
import { motion } from 'framer-motion';
import { ShoppingCart, Zap, Star, AlertCircle, MessageCircle } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMyPlayerQueryKey } from '@workspace/api-client-react';

export default function Shop() {
  const [tab, setTab] = useState<'items' | 'premium'>('items');
  const { data: items, isLoading: itemsLoading } = useListShopItems();
  const { data: packs, isLoading: packsLoading } = useListPremiumPacks();
  const purchaseMutation = usePurchaseShopItem();
  const queryClient = useQueryClient();

  const handlePurchase = async (itemId: number) => {
    try {
      await purchaseMutation.mutateAsync({ data: { item_id: itemId, quantity: 1 } });
      queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-8 pb-12">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold mb-2">Cursed Shop</h1>
          <p className="text-muted-foreground">Purchase items, weapons, and special upgrades.</p>
        </div>
        
        <div className="flex bg-black/40 rounded-lg p-1 border border-white/10">
          <button 
            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'items' ? 'bg-primary text-white shadow-lg' : 'text-muted-foreground hover:text-white'}`}
            onClick={() => setTab('items')}
          >
            In-Game Items
          </button>
          <button 
            className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'premium' ? 'bg-secondary text-white shadow-lg' : 'text-muted-foreground hover:text-white'}`}
            onClick={() => setTab('premium')}
          >
            Premium Store
          </button>
        </div>
      </div>

      {tab === 'items' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {itemsLoading ? (
            [...Array(6)].map((_, i) => <div key={i} className="h-64 glass-card animate-pulse rounded-xl"></div>)
          ) : (
            items?.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="h-full flex flex-col hover:border-primary/50 transition-colors group relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-primary/10 rounded-full blur-[50px] group-hover:bg-primary/20 transition-colors pointer-events-none" />
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <Badge variant="outline" className="mb-2 text-xs border-primary/30 text-primary">{item.type.toUpperCase()}</Badge>
                      <div className="font-mono font-bold text-yellow-400 text-lg flex items-center gap-1">
                        ¥{item.price.toLocaleString()}
                      </div>
                    </div>
                    <CardTitle className="text-xl">{item.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="flex-1 flex flex-col justify-between pt-0 mt-[-10px]">
                    <p className="text-sm text-muted-foreground mb-6 line-clamp-3">{item.description}</p>
                    <Button 
                      className="w-full mt-auto" 
                      onClick={() => handlePurchase(item.id)}
                      disabled={purchaseMutation.isPending}
                    >
                      <ShoppingCart size={16} className="mr-2" /> Purchase
                    </Button>
                  </CardContent>
                </Card>
              </motion.div>
            ))
          )}
        </div>
      )}

      {tab === 'premium' && (
        <div className="space-y-8">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="bg-gradient-to-r from-secondary/20 to-primary/10 border-secondary/30 relative overflow-hidden">
              <div className="absolute right-0 top-0 w-1/3 h-full bg-gradient-to-l from-black/50 to-transparent pointer-events-none" />
              <CardContent className="p-8 md:p-12 flex flex-col md:flex-row items-center justify-between relative z-10">
                <div className="max-w-xl mb-6 md:mb-0 text-center md:text-left">
                  <h2 className="text-3xl font-display font-bold mb-4 bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">Need More Yen?</h2>
                  <p className="text-muted-foreground text-lg mb-2">Instantly boost your balance or grab exclusive elixirs through our verified seller.</p>
                  <div className="flex items-center justify-center md:justify-start gap-2 text-sm text-yellow-400 font-mono">
                    <Star size={16} className="fill-yellow-400" /> Fast Delivery · Secure Transaction
                  </div>
                </div>
                <a href="https://t.me/victory_tech" target="_blank" rel="noopener noreferrer" className="shrink-0">
                  <Button size="lg" className="bg-blue-600 hover:bg-blue-500 text-white border-0 shadow-[0_0_20px_rgba(37,99,235,0.4)] text-lg px-8 py-6 rounded-xl h-auto">
                    <MessageCircle className="mr-3 h-6 w-6" /> Contact @victory_tech
                  </Button>
                </a>
              </CardContent>
            </Card>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {packsLoading ? (
               [...Array(3)].map((_, i) => <div key={i} className="h-80 glass-card animate-pulse rounded-xl"></div>)
            ) : (
              packs?.map((pack, i) => (
                <motion.div
                  key={pack.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <Card className={`h-full flex flex-col relative overflow-hidden ${pack.is_featured ? 'border-yellow-500/50 shadow-[0_0_30px_rgba(234,179,8,0.15)]' : 'border-white/10'}`}>
                    {pack.is_featured && (
                      <div className="absolute top-4 right-4 bg-yellow-500 text-black text-xs font-bold px-3 py-1 rounded-full shadow-[0_0_10px_rgba(234,179,8,0.5)]">
                        BEST VALUE
                      </div>
                    )}
                    <CardHeader className="text-center pt-8">
                      <div className="w-16 h-16 mx-auto bg-gradient-to-br from-yellow-400/20 to-yellow-600/20 rounded-full flex items-center justify-center mb-4 border border-yellow-500/30">
                        {pack.category === 'yen' ? <Coins className="text-yellow-400" size={32} /> : 
                         pack.category === 'elixir' ? <Zap className="text-blue-400" size={32} /> : 
                         <Star className="text-purple-400" size={32} />}
                      </div>
                      <CardTitle className="text-2xl mb-2">{pack.name}</CardTitle>
                      <div className="text-3xl font-mono font-bold text-white mb-2">${pack.price_usd.toFixed(2)}</div>
                      {pack.bonus_label && (
                        <div className="text-sm font-bold text-green-400 uppercase tracking-wider">{pack.bonus_label}</div>
                      )}
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col mt-4">
                      <p className="text-center text-muted-foreground mb-8 text-sm">{pack.description}</p>
                      
                      <a href="https://t.me/victory_tech" target="_blank" rel="noopener noreferrer" className="mt-auto">
                        <Button variant="outline" className="w-full border-yellow-500/50 text-yellow-500 hover:bg-yellow-500/10 hover:text-yellow-400">
                          Request via Telegram
                        </Button>
                      </a>
                    </CardContent>
                  </Card>
                </motion.div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Temporary Coins icon for the file since it's not imported at top
const Coins = ({ size, className }: { size?: number, className?: string }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinelinejoin="round" className={className}><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.49-.98"/><path d="m14.48 15.65.6-.92"/></svg>
);
