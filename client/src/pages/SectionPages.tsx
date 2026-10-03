import MarketPanel from '@/pages/MarketPanel';
import TopupPanel from '@/pages/TopupPanel';
import Inventory from '@/pages/Inventory';
import type { InventoryItem } from '@/lib/jjk-api';
export function MarketPage({ onBalanceChange }: { onBalanceChange: (yen: number) => void }) { return <div className="page-wrap"><div className="page-heading"><div><p className="eyebrow text-[#ab75ff]">Exchange // in-game only</p><h1 className="page-title">The curse economy.</h1><p className="page-lede">Trade fictional assets with real player yen and build a position worth defending.</p></div></div><MarketPanel onBalanceChange={onBalanceChange} /></div>; }
export function TreasuryPage() { return <div className="page-wrap"><div className="page-heading"><div><p className="eyebrow text-[#9be15d]">Treasury // manual review</p><h1 className="page-title">Fund your progression.</h1><p className="page-lede">Use OPay, send your receipt, and wait for owner verification before yen enters the game.</p></div></div><TopupPanel /></div>; }
export function InventoryPage({ items, loading, error, actionId, onEquip, onBack }: { items: InventoryItem[]; loading: boolean; error: string; actionId: number | null; onEquip: (item: InventoryItem) => void; onBack: () => void }) { return <Inventory items={items} loading={loading} error={error} actionId={actionId} onEquip={onEquip} onBack={onBack} />; }
