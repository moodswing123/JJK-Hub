import React, { useState } from 'react';
import { useListTransactions, useCreateManualPurchase } from '@workspace/api-client-react';
import { Card, CardContent, CardHeader, CardTitle, Button, Input, Badge } from '@/components/ui/core';
import { motion } from 'framer-motion';
import { format } from 'date-fns';
import { MessageCircle, Receipt } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { getListTransactionsQueryKey } from '@workspace/api-client-react';

export default function Transactions() {
  const { data: transactions, isLoading } = useListTransactions({ limit: 50 });
  const [yenAmount, setYenAmount] = useState('');
  const purchaseMutation = useCreateManualPurchase();
  const queryClient = useQueryClient();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!yenAmount) return;
    
    try {
      await purchaseMutation.mutateAsync({ data: { yen_amount: Number(yenAmount) } });
      queryClient.invalidateQueries({ queryKey: getListTransactionsQueryKey({limit: 50}) });
      setYenAmount('');
      // In a real app we'd redirect to Telegram or show a modal with the contact link
      window.open('https://t.me/victory_tech', '_blank');
    } catch(err) {}
  };

  return (
    <div className="space-y-8 pb-12 max-w-5xl mx-auto">
      <h1 className="text-3xl font-display font-bold mb-8">Transaction History</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          <Card className="overflow-hidden">
            <div className="p-4 border-b border-white/5 bg-white/[0.02] text-xs font-mono text-muted-foreground uppercase tracking-widest grid grid-cols-12 gap-4">
              <div className="col-span-4">Type / ID</div>
              <div className="col-span-3 text-right">Amount</div>
              <div className="col-span-2 text-center">Status</div>
              <div className="col-span-3 text-right">Date</div>
            </div>
            
            <div className="min-h-[400px]">
              {isLoading ? (
                <div className="p-4 space-y-4">
                  {[...Array(5)].map((_, i) => <div key={i} className="h-16 bg-white/5 animate-pulse rounded-lg"></div>)}
                </div>
              ) : transactions?.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                  <Receipt size={48} className="mb-4 opacity-20" />
                  <p>No transactions found.</p>
                </div>
              ) : (
                <div className="p-4 flex flex-col gap-2">
                  {transactions?.map(tx => (
                    <div key={tx.id} className="grid grid-cols-12 gap-4 p-4 rounded-lg hover:bg-white/5 transition-colors items-center border border-transparent hover:border-white/10">
                      <div className="col-span-4">
                        <div className="font-bold capitalize">{tx.type.replace('_', ' ')}</div>
                        <div className="text-xs font-mono text-muted-foreground">TX-{tx.id}</div>
                      </div>
                      <div className="col-span-3 text-right font-mono">
                        {tx.currency === 'USD' ? `$${tx.amount.toFixed(2)}` : `${tx.amount} ${tx.currency}`}
                      </div>
                      <div className="col-span-2 flex justify-center">
                        <Badge variant="outline" className={`text-[10px] ${
                          tx.status === 'completed' ? 'border-green-500/30 text-green-400' :
                          tx.status === 'pending' ? 'border-yellow-500/30 text-yellow-400' :
                          'border-red-500/30 text-red-400'
                        }`}>
                          {tx.status.toUpperCase()}
                        </Badge>
                      </div>
                      <div className="col-span-3 text-right text-xs text-muted-foreground">
                        {format(new Date(tx.created_at), 'MMM d, yyyy')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="border-primary/20 bg-primary/5">
            <CardHeader>
              <CardTitle className="text-lg">Request Yen Purchase</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <p className="text-sm text-muted-foreground mb-4">
                  Enter the amount of Yen you want to buy. This creates a pending request. Contact our verified seller on Telegram to complete payment.
                </p>
                <div>
                  <label className="text-xs text-muted-foreground uppercase tracking-widest mb-1 block">Yen Amount</label>
                  <Input 
                    type="number" 
                    placeholder="e.g. 10000" 
                    value={yenAmount}
                    onChange={e => setYenAmount(e.target.value)}
                    min="1000"
                    required
                    className="bg-black/50"
                  />
                </div>
                <Button type="submit" className="w-full gap-2" disabled={purchaseMutation.isPending}>
                  <MessageCircle size={16} /> Create Request & Contact
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}