import { useEffect, useMemo, useState } from 'react';
import { Banknote, CheckCircle2, FileUp, Loader2, ShieldCheck } from 'lucide-react';
import { jjkApi, type TopupInfo } from '@/lib/jjk-api';

type Props = { onBalanceChange?: (yen: number) => void };
const formatYen = (value: number) => `¥${value.toLocaleString()}`;
const formatNaira = (value: number) => `₦${value.toLocaleString()}`;

export default function TopupPanel({ onBalanceChange: _onBalanceChange }: Props) {
  const [info, setInfo] = useState<TopupInfo | null>(null);
  const [selection, setSelection] = useState('100000');
  const [custom, setCustom] = useState('');
  const [reference, setReference] = useState('');
  const [receipt, setReceipt] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const isCustom = selection === 'custom';
  const yenAmount = isCustom ? Number(custom) : Number(selection);
  const nairaAmount = Number.isFinite(yenAmount) && yenAmount > 0 ? Math.ceil(yenAmount / (info?.rate_yen_per_naira || 1000)) : 0;
  const selectedPackage = useMemo(() => info?.packages?.find(item => item.yen === yenAmount), [info, yenAmount]);

  useEffect(() => { jjkApi.topupInfo().then(setInfo).catch(() => setError('Payment instructions are unavailable.')); }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!Number.isInteger(yenAmount) || yenAmount < 1) return setError('Enter a whole-number yen amount greater than zero.');
    if (!receipt) return setError('Choose your payment receipt first.');
    setBusy(true); setError(''); setMessage('');
    try {
      const result = await jjkApi.submitTopup(yenAmount, reference, receipt);
      setMessage(`${result.message} Request #${result.topup_id}.`);
      setReference(''); setReceipt(null);
      if (isCustom) setCustom('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not submit receipt.'); }
    finally { setBusy(false); }
  }

  return <section className="panel topup-glow mt-5 p-6 sm:p-8" aria-label="Buy yen">
    <div className="relative grid gap-7 lg:grid-cols-[.9fr_1.1fr] lg:items-start">
      <div>
        <div className="mb-2 flex items-center gap-2"><Banknote size={15} className="text-[#9be15d]" /><p className="eyebrow text-[#9be15d]">Treasury // buy yen</p></div>
        <h2 className="font-display text-2xl font-semibold sm:text-3xl">Fund your next awakening.</h2>
        <p className="mt-2 text-sm leading-6 text-[#9aa7bc]">Choose a package or enter a custom amount. The conversion is fixed at <b className="text-[#d8f6b7]">100,000 yen = ₦100</b>, so you always know exactly what to send.</p>
        <div className="mt-6 border border-[#9be15d]/25 bg-[#9be15d]/10 p-5">
          <p className="eyebrow text-[#9be15d]">Payment destination</p>
          {info ? <><p className="mt-3 font-display text-lg font-semibold">{info.account_name}</p><p className="mt-1 font-mono text-xl text-[#d8f6b7]">{info.account_number}</p><p className="mt-1 text-xs uppercase tracking-[.16em] text-[#9aa7bc]">{info.provider}</p></> : <span className="mt-3 block text-sm text-[#8795aa]">Loading secure instructions…</span>}
          <div className="mt-4 flex items-start gap-2 border-t border-white/10 pt-4 text-xs leading-5 text-[#9aa7bc]"><ShieldCheck size={15} className="mt-0.5 shrink-0 text-[#9be15d]" /> Send the exact naira amount shown below. Yen is credited automatically after approval.</div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {(info?.packages || [{ yen: 100000, naira: 100 }, { yen: 250000, naira: 250 }, { yen: 500000, naira: 500 }, { yen: 750000, naira: 750 }, { yen: 1000000, naira: 1000 }]).map(item => <button key={item.yen} type="button" onClick={() => { setSelection(String(item.yen)); setError(''); }} className={`rounded border p-3 text-left transition ${!isCustom && yenAmount === item.yen ? 'border-[#9be15d] bg-[#9be15d]/15' : 'border-white/10 bg-white/[.02] hover:border-[#9be15d]/50'}`}><b className="block font-mono text-sm text-[#d8f6b7]">{formatYen(item.yen)}</b><small className="mt-1 block text-xs text-[#9aa7bc]">Send {formatNaira(item.naira)}</small></button>)}
          <button type="button" onClick={() => { setSelection('custom'); setError(''); }} className={`rounded border p-3 text-left transition ${isCustom ? 'border-[#55d8e5] bg-[#55d8e5]/10' : 'border-white/10 bg-white/[.02] hover:border-[#55d8e5]/50'}`}><b className="block text-sm text-[#bfeff3]">Custom amount</b><small className="mt-1 block text-xs text-[#9aa7bc]">Calculated at 1,000 yen/₦1</small></button>
        </div>
      </div>
      <form onSubmit={submit} className="border border-white/10 bg-[#080e18]/70 p-5">
        <p className="eyebrow mb-5">Submit proof // owner review</p>
        {isCustom && <><label className="field-label" htmlFor="topup-custom">Custom yen amount</label><div className="input-wrap"><span className="text-[#ffd166]">¥</span><input id="topup-custom" type="number" min="1" step="1" value={custom} onChange={event => setCustom(event.target.value)} placeholder="125000" required /></div></>}
        <div className="border border-[#ffd166]/30 bg-[#ffd166]/10 p-4"><p className="eyebrow text-[#ffd166]">Amount to send</p><p className="mt-2 font-display text-2xl font-semibold text-[#fff0bd]">{nairaAmount ? formatNaira(nairaAmount) : '—'}</p><p className="mt-1 text-xs text-[#c5b98d]">For {yenAmount > 0 ? formatYen(yenAmount) : 'your yen amount'}{selectedPackage ? ' package' : ''}</p></div>
        <label className="field-label mt-4" htmlFor="topup-reference">Payment reference</label><div className="input-wrap"><input id="topup-reference" value={reference} onChange={event => setReference(event.target.value)} placeholder="OPay transaction reference" required /></div>
        <label className="field-label mt-4" htmlFor="receipt">Receipt file</label><label htmlFor="receipt" className="mt-1 flex cursor-pointer items-center gap-3 border border-dashed border-white/20 bg-white/[.02] px-4 py-4 text-xs text-[#a8b4c8] transition hover:border-[#55d8e5]/60"><FileUp size={17} className="text-[#55d8e5]" /><span>{receipt ? receipt.name : 'JPG, PNG, WEBP, or PDF · max 5 MB'}</span><input id="receipt" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="sr-only" onChange={event => setReceipt(event.target.files?.[0] || null)} /></label>
        <button type="submit" disabled={busy} className="mt-5 flex w-full items-center justify-center gap-2 bg-[#9be15d] px-4 py-3 text-sm font-semibold text-[#10170c] transition hover:brightness-110 disabled:opacity-60">{busy ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} />}{busy ? 'Sending receipt…' : 'Send receipt for review'}</button>
        {(message || error) && <p role={error ? 'alert' : 'status'} className={`mt-4 border p-3 text-xs ${error ? 'border-[#f05b63]/30 bg-[#f05b63]/10 text-[#ffafb3]' : 'border-[#9be15d]/30 bg-[#9be15d]/10 text-[#c8f69f]'}`}>{message || error}</p>}
      </form>
    </div>
  </section>;
}
