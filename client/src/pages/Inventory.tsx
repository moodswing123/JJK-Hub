// Obsidian Command Deck inventory page: present cursed tools as a practical player loadout, with clear state and restrained signal-coral actions.
import { motion } from 'framer-motion';
import { ArrowLeft, Axe, Check, Gem, PackageOpen, Shield, Swords, WandSparkles } from 'lucide-react';

export type InventoryItem = { id: number; name: string; type?: string; price?: number; description?: string; use_description?: string; effect?: Record<string, number> | string | null };

type Props = { items: InventoryItem[]; loading: boolean; error: string; onBack: () => void; onEquip: (item: InventoryItem) => void; actionId: number | null };

function itemIcon(type?: string) {
  if (type === 'weapon') return Swords;
  if (type === 'armor') return Shield;
  if (type === 'accessory') return Gem;
  return WandSparkles;
}

function effects(item: InventoryItem) {
  if (!item.effect) return [];
  if (typeof item.effect === 'object') return Object.entries(item.effect);
  try { return Object.entries(JSON.parse(item.effect) as Record<string, number>); } catch { return []; }
}

export default function Inventory({ items, loading, error, onBack, onEquip, actionId }: Props) {
  const tools = items.filter((item) => item.type === 'weapon' || item.type === 'armor' || item.type === 'accessory');
  return <motion.main className="min-h-screen bg-[#080b10] text-[#f4eee6]" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
    <header className="sticky top-0 z-20 border-b border-white/10 bg-[#080b10]/90 backdrop-blur-xl"><div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-5 lg:px-10"><button type="button" onClick={onBack} className="flex items-center gap-2 text-xs uppercase tracking-[.16em] text-[#89919d] transition hover:text-white"><ArrowLeft size={15} /> Overview</button><span className="font-display text-lg font-semibold">JJK RPG <span className="ml-2 text-xs font-normal uppercase tracking-[.18em] text-[#717984]">Inventory</span></span></div></header>
    <section className="mx-auto max-w-[1440px] px-5 py-8 lg:px-10 lg:py-12"><div className="flex flex-col justify-between gap-5 border-b border-white/10 pb-8 sm:flex-row sm:items-end"><div><p className="eyebrow mb-2 text-[#ef5b68]">Arsenal // cursed tools</p><h1 className="font-display text-4xl font-semibold tracking-[-.04em] sm:text-6xl">Your inventory.</h1><p className="mt-3 max-w-xl text-sm leading-6 text-[#89919d]">Review every tool in your possession and equip weapons when you are ready to return to battle.</p></div><div className="flex items-center gap-3 text-xs text-[#89919d]"><PackageOpen size={16} className="text-[#ef5b68]" /> {tools.length} cursed tools</div></div>
      {error && <p role="alert" className="mt-6 border border-[#ef5b68]/30 bg-[#ef5b68]/10 p-4 text-sm text-[#ffadb4]">{error}</p>}
      {loading ? <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[1,2,3].map((key) => <div key={key} className="h-56 animate-pulse border border-white/10 bg-[#10141b]" />)}</div> : tools.length === 0 ? <div className="mt-8 border border-dashed border-white/15 bg-[#10141b]/60 px-6 py-16 text-center"><PackageOpen className="mx-auto text-[#ef5b68]" size={30} /><h2 className="mt-4 font-display text-2xl font-semibold">Your arsenal is empty.</h2><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-[#89919d]">Purchase cursed tools through the JJK RPG bot, then return here to manage your loadout.</p></div> : <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">{tools.map((item, index) => { const Icon = itemIcon(item.type); const itemEffects = effects(item); const equippable = item.type === 'weapon'; return <motion.article key={item.id} className="group border border-white/10 bg-[#10141b] p-5 transition hover:-translate-y-1 hover:border-[#ef5b68]/45 hover:bg-[#141922]" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .05 }}><div className="flex items-start justify-between"><div className="flex h-12 w-12 items-center justify-center border border-[#ef5b68]/25 bg-[#ef5b68]/10 text-[#ef5b68]"><Icon size={22} /></div><span className="eyebrow">{item.type || 'cursed tool'}</span></div><h2 className="mt-6 font-display text-2xl font-semibold">{item.name}</h2><p className="mt-2 min-h-12 text-sm leading-6 text-[#89919d]">{item.description || item.use_description || 'A recovered tool from the curse field.'}</p>{itemEffects.length > 0 && <div className="mt-5 flex flex-wrap gap-2">{itemEffects.map(([key, value]) => <span key={key} className="badge">+{value} {key.toUpperCase()}</span>)}</div>}<button type="button" disabled={!equippable || actionId === item.id} onClick={() => onEquip(item)} className="mt-6 flex w-full items-center justify-center gap-2 border border-white/10 px-4 py-3 text-xs font-semibold uppercase tracking-[.14em] text-[#d9d6d0] transition hover:border-[#ef5b68] hover:text-[#ef5b68] disabled:cursor-not-allowed disabled:opacity-50">{actionId === item.id ? <><span className="spinner" /> Equipping…</> : equippable ? <><Axe size={14} /> Equip tool</> : <><Check size={14} /> Held in inventory</>}</button></motion.article>; })}</div>}
    </section>
  </motion.main>;
}
