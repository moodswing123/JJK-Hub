import { useEffect, useMemo, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, CircleDollarSign, Loader2, RefreshCw, Sparkles, TrendingUp } from 'lucide-react';
import { jjkApi, type MarketAsset, type MarketSnapshot } from '@/lib/jjk-api';

type Props = { onBalanceChange?: (yen: number) => void };

export default function MarketPanel({ onBalanceChange }: Props) {
  const [market, setMarket] = useState<MarketSnapshot | null>(null);
  const [selected, setSelected] = useState<MarketAsset | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [loading, setLoading] = useState(true);
  const [trading, setTrading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function load() {
    setLoading(true); setError('');
    try { const result = await jjkApi.market(); setMarket(result); setSelected((current) => result.assets.find((asset) => asset.asset_id === current?.asset_id) || result.assets[0] || null); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Market data is unavailable.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  const owned = useMemo(() => market?.holdings.find((holding) => holding.asset_id === selected?.asset_id)?.quantity || 0, [market, selected]);
  const total = (selected?.price || 0) * Math.max(1, quantity);

  async function placeOrder() {
    if (!selected || trading) return;
    setTrading(true); setError(''); setMessage('');
    try {
      const result = await jjkApi.trade(selected.asset_id, side, Math.max(1, quantity));
      onBalanceChange?.(result.balance);
      setMessage(`${side === 'buy' ? 'Bought' : 'Sold'} ${quantity} ${selected.ticker} for ¥${result.total.toLocaleString()}.`);
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Order could not be settled.'); }
    finally { setTrading(false); }
  }

  return <section className="panel market-glow mt-5 p-6 sm:p-8" aria-label="In-game market exchange"><div className="relative flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="mb-2 flex items-center gap-2"><Sparkles size={14} className="text-[#ab75ff]" /><p className="eyebrow text-[#ab75ff]">Market // in-game exchange</p></div><h2 className="font-display text-2xl font-semibold sm:text-3xl">Convert yen into leverage.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-[#9aa7bc]">Trade fictional cursed assets with your earned yen. Every order is checked and settled on the server against your main player balance.</p></div><div className="border border-[#ffd166]/30 bg-[#ffd166]/10 px-4 py-3"><p className="eyebrow text-[#ffd166]">Available yen</p><p className="mt-1 font-mono text-lg font-semibold text-[#ffe29a]">¥{(market?.yen || 0).toLocaleString()}</p></div></div>{loading ? <div className="relative flex min-h-36 items-center justify-center"><Loader2 className="animate-spin text-[#55d8e5]" /></div> : error && !market ? <div className="relative mt-6 border border-[#f05b63]/30 bg-[#f05b63]/10 p-4 text-sm text-[#ffafb3]">{error}</div> : <><div className="relative mt-7 grid gap-3 md:grid-cols-3">{(market?.assets || []).map((asset, index) => <button type="button" key={asset.asset_id} onClick={() => { setSelected(asset); setError(''); }} className={`text-left border p-4 transition hover:-translate-y-1 ${selected?.asset_id === asset.asset_id ? 'border-[#55d8e5] bg-[#102536]' : 'border-white/10 bg-[#080e18]/75 hover:border-[#55d8e5]/50'}`}><div className="flex items-start justify-between"><div><p className="font-mono text-xs text-[#d7dfed]">{asset.ticker}</p><p className="mt-1 text-xs text-[#8694aa]">{asset.name}</p></div>{asset.change_percent >= 0 ? <TrendingUp size={16} className="tone-green" /> : <ArrowDownRight size={16} className="text-[#ab75ff]" />}</div><div className="mt-5 flex items-end justify-between"><p className="font-mono text-xl font-semibold">¥{asset.price.toLocaleString()}</p><span className={`text-xs font-semibold ${asset.change_percent >= 0 ? 'tone-green' : 'text-[#ab75ff]'}`}>{asset.change_percent >= 0 ? '+' : ''}{asset.change_percent.toFixed(1)}%</span></div><div className="market-line mt-4" style={{ opacity: .45 + index * .16 }} /></button>)}</div><div className="relative mt-5 grid gap-4 border-t border-white/10 pt-5 lg:grid-cols-[1fr_auto] lg:items-end"><div><p className="eyebrow mb-2">Order ticket {selected ? `// ${selected.ticker}` : ''}</p><div className="flex flex-wrap items-end gap-3"><label className="text-xs text-[#9aa7bc]">Side<select value={side} onChange={(event) => setSide(event.target.value as 'buy' | 'sell')} className="mt-1 block border border-white/10 bg-[#080e18] px-3 py-2 text-sm text-[#f6f1e8]"><option value="buy">Buy</option><option value="sell">Sell</option></select></label><label className="text-xs text-[#9aa7bc]">Quantity<input type="number" min={1} max={100000} value={quantity} onChange={(event) => setQuantity(Math.max(1, Number(event.target.value) || 1))} className="mt-1 block w-28 border border-white/10 bg-[#080e18] px-3 py-2 font-mono text-sm text-[#f6f1e8]" /></label><div className="pb-2 text-xs text-[#9aa7bc]">Owned: <span className="font-mono text-[#f6f1e8]">{owned}</span><br />Order total: <span className="font-mono text-[#ffd166]">¥{total.toLocaleString()}</span></div></div></div><button type="button" disabled={!selected || trading} onClick={placeOrder} className="inline-flex items-center justify-center gap-2 bg-[#f05b63] px-5 py-3 text-sm font-semibold text-[#180a11] transition hover:brightness-110 active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-60">{trading ? <Loader2 size={15} className="animate-spin" /> : <CircleDollarSign size={15} />}{trading ? 'Settling order…' : `${side === 'buy' ? 'Buy' : 'Sell'} ${selected?.ticker || 'asset'}`}</button></div>{(message || error) && <p role={error ? 'alert' : 'status'} className={`relative mt-4 border p-3 text-xs ${error ? 'border-[#f05b63]/30 bg-[#f05b63]/10 text-[#ffafb3]' : 'border-[#9be15d]/30 bg-[#9be15d]/10 text-[#c8f69f]'}`}>{message || error}</p>}<div className="relative mt-5 flex flex-col gap-3 border-t border-white/10 pt-4 text-xs text-[#8795aa] sm:flex-row sm:items-center sm:justify-between"><span className="flex items-center gap-2"><span className="pulse-dot" /> Fictional game economy · yen only · no real-money trading</span><button type="button" onClick={() => void load()} className="inline-flex items-center gap-2 self-start border border-[#55d8e5]/30 px-3 py-2 font-semibold text-[#55d8e5] transition hover:border-[#55d8e5] hover:bg-[#55d8e5]/10"><RefreshCw size={13} /> Refresh market</button></div></>}</section>;
}
