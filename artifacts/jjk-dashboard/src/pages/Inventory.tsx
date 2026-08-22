import React, { useState } from 'react';
import { useListInventory, useUseItem, useSellItem } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Button, Badge, Input } from '@/components/ui/core';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Filter, FlaskConical, Sword, Sparkles } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMyPlayerQueryKey, getListInventoryQueryKey } from '@workspace/api-client-react';

const TYPE_ICONS: Record<string, React.ReactNode> = {
  'consumable': <FlaskConical size={16} className="text-green-400" />,
  'weapon': <Sword size={16} className="text-red-400" />,
  'special': <Sparkles size={16} className="text-purple-400" />,
};

const TYPE_COLORS: Record<string, string> = {
  'consumable': 'border-green-500/30 bg-green-500/10 text-green-400',
  'weapon': 'border-red-500/30 bg-red-500/10 text-red-400',
  'special': 'border-purple-500/30 bg-purple-500/10 text-purple-400',
};

export default function Inventory() {
  const { data: inventory, isLoading } = useListInventory();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string | null>(null);
  
  const useMutation = useUseItem();
  const sellMutation = useSellItem();
  const queryClient = useQueryClient();

  const filtered = inventory?.filter(item => {
    if (filterType && item.type !== filterType) return false;
    if (search && !item.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  }) || [];

  const types = Array.from(new Set(inventory?.map(i => i.type) || []));

  const handleUse = async (id: number) => {
    try {
      await useMutation.mutateAsync({ itemId: id });
      queryClient.invalidateQueries({ queryKey: getListInventoryQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
    } catch(e) {}
  };

  const handleSell = async (id: number) => {
    try {
      await sellMutation.mutateAsync({ itemId: id });
      queryClient.invalidateQueries({ queryKey: getListInventoryQueryKey() });
      queryClient.invalidateQueries({ queryKey: getGetMyPlayerQueryKey() });
    } catch(e) {}
  };

  return (
    <div className="space-y-8 pb-12">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold mb-2">Inventory</h1>
          <p className="text-muted-foreground">Manage your items, weapons, and consumables.</p>
        </div>
        
        <div className="flex items-center gap-4 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} />
            <Input 
              placeholder="Search items..." 
              className="pl-10 bg-black/40 border-white/10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
        <Badge 
          variant={filterType === null ? 'default' : 'outline'} 
          className="cursor-pointer px-4 py-1.5 text-sm"
          onClick={() => setFilterType(null)}
        >
          All Items
        </Badge>
        {types.map(type => (
          <Badge 
            key={type}
            variant={filterType === type ? 'default' : 'outline'} 
            className="cursor-pointer px-4 py-1.5 text-sm capitalize border-white/10 hover:border-white/30 transition-colors"
            onClick={() => setFilterType(type)}
          >
            {type}
          </Badge>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => <div key={i} className="h-64 glass-card animate-pulse rounded-xl"></div>)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-20 text-center glass-card border-dashed border-2 border-white/10 rounded-xl">
          <Filter className="mx-auto mb-4 text-muted-foreground opacity-50" size={48} />
          <p className="text-xl font-display font-bold text-muted-foreground">Empty Space</p>
          <p className="text-sm text-muted-foreground mt-2">No items found matching your criteria.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          <AnimatePresence>
            {filtered.map((item, i) => (
              <motion.div
                layout
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.2 }}
                key={`${item.id}-${i}`} // item.id might not be unique if multiple of same item without stacking, but usually stacked
              >
                <Card className="h-full flex flex-col bg-gradient-to-b from-white/[0.02] to-transparent border-white/5 hover:border-white/20 transition-all">
                  <CardHeader className="pb-4">
                    <div className="flex justify-between items-start mb-3">
                      <div className={`p-2 rounded-lg border ${TYPE_COLORS[item.type] || 'border-white/20 bg-white/5'}`}>
                        {TYPE_ICONS[item.type] || <Sparkles size={16} />}
                      </div>
                      {item.quantity && item.quantity > 1 && (
                        <Badge variant="secondary" className="bg-white/10 font-mono">x{item.quantity}</Badge>
                      )}
                    </div>
                    <CardTitle className="text-lg leading-tight">{item.name}</CardTitle>
                    <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest">{item.type}</div>
                  </CardHeader>
                  
                  <CardContent className="flex-1 flex flex-col justify-between pt-0">
                    <div className="space-y-4 mb-6">
                      <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
                      {item.effect && (
                        <div className="bg-black/40 border border-white/5 p-2 rounded text-xs text-primary font-mono text-center">
                          {item.effect}
                        </div>
                      )}
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 mt-auto">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="w-full text-xs"
                        onClick={() => handleSell(item.id)}
                        disabled={sellMutation.isPending}
                      >
                        Sell (¥{Math.floor(item.price * 0.5)})
                      </Button>
                      <Button 
                        size="sm" 
                        className="w-full text-xs"
                        onClick={() => handleUse(item.id)}
                        disabled={useMutation.isPending || item.type === 'weapon'}
                      >
                        {item.type === 'weapon' ? 'Equip' : 'Use'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
