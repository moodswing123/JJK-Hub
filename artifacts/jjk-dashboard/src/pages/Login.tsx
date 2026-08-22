import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Bot, LockKeyhole, Radio, ShieldCheck } from 'lucide-react';
import { useLocation } from 'wouter';
import { useTelegramLogin } from '@workspace/api-client-react';
import { setAuthTokenGetter } from '@workspace/api-client-react/custom-fetch';
import { Card, Button } from '@/components/ui/core';

type TelegramUser = {
  id: number;
  first_name: string;
  last_name?: string | null;
  username?: string | null;
  photo_url?: string | null;
  auth_date: number;
  hash: string;
};

export default function Login() {
  const [, setLocation] = useLocation();
  const loginMutation = useTelegramLogin();
  const widgetContainer = useRef<HTMLDivElement>(null);
  const botUsername = import.meta.env.VITE_TELEGRAM_BOT_USERNAME?.trim().replace(/^@+/, '');

  useEffect(() => {
    const token = localStorage.getItem('jjk_token');
    if (token) { setAuthTokenGetter(() => token); setLocation('/dashboard'); }
  }, [setLocation]);

  useEffect(() => {
    const container = widgetContainer.current;
    if (!container) return;
    container.innerHTML = '';
    if (!botUsername) return;
    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.async = true;
    script.setAttribute('data-telegram-login', botUsername);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-radius', '10');
    script.setAttribute('data-request-access', 'write');
    script.setAttribute('data-userpic', 'false');
    script.setAttribute('data-onauth', 'onTelegramAuth(user)');
    (window as unknown as { onTelegramAuth?: (user: TelegramUser) => void }).onTelegramAuth = async (user: TelegramUser) => {
      try {
        const result = await loginMutation.mutateAsync({ data: user });
        if (result.token) { localStorage.setItem('jjk_token', result.token); setAuthTokenGetter(() => result.token); setLocation('/dashboard'); }
      } catch (error) { console.error('Telegram authentication failed', error); }
    };
    container.appendChild(script);
    return () => { container.innerHTML = ''; delete (window as unknown as { onTelegramAuth?: unknown }).onTelegramAuth; };
  }, [botUsername, loginMutation, setLocation]);

  return <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12"><div className="pointer-events-none absolute inset-0 bg-grid-pattern opacity-60" /><div className="pointer-events-none absolute left-1/2 top-1/2 h-[34rem] w-[34rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/10 blur-[130px]" />
    <div className="relative z-10 w-full max-w-[28rem]"><div className="mb-10 text-center"><div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-2xl shadow-primary/25"><Bot size={30} /></div><p className="section-label mb-3 text-primary">JJK RPG // Secure gateway</p><h1 className="font-display text-4xl font-semibold tracking-tight sm:text-5xl">Enter the realm.</h1><p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-muted-foreground">Your command center for progression, combat, and cursed energy management.</p></div>
      <Card className="border-border/80 bg-card/90 p-1 shadow-2xl shadow-black/30"><div className="rounded-xl border border-border/50 bg-background/30 p-6 sm:p-8"><div className="mb-8 flex items-center justify-between"><div><p className="section-label mb-1">Identity check</p><h2 className="text-xl font-semibold">Connect Telegram</h2></div><LockKeyhole size={20} className="text-primary" /></div><p className="mb-7 text-sm leading-6 text-muted-foreground">Sign in with the Telegram account linked to your JJK RPG character. Your player data stays synchronized with the game.</p>
        {loginMutation.isPending ? <div className="flex flex-col items-center gap-4 rounded-xl border border-border/60 bg-muted/30 py-8"><div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" /><p className="text-sm text-muted-foreground">Verifying your sorcerer identity…</p></div> : !botUsername ? <div className="rounded-xl border border-amber-400/25 bg-amber-400/10 p-4 text-sm leading-6 text-amber-100">Telegram login is not configured. Set <code className="font-mono text-xs">VITE_TELEGRAM_BOT_USERNAME</code> in the frontend deployment.</div> : <div ref={widgetContainer} className="flex min-h-12 justify-center" data-testid="telegram-login-widget" />}
        {loginMutation.isError && <p className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-center text-xs text-destructive-foreground">Authentication was declined. Please try connecting again.</p>}
        <div className="mt-8 grid grid-cols-3 gap-2 border-t border-border/60 pt-5 text-center"><Trust icon={ShieldCheck} label="Verified" /><Trust icon={Radio} label="Live sync" /><Trust icon={ArrowRight} label="Fast entry" /></div>
      </div></Card><p className="mt-6 text-center text-xs text-muted-foreground">Need Yen or support? <a className="text-accent hover:underline" href="https://t.me/victory_tech" target="_blank" rel="noreferrer">Contact @victory_tech</a></p></div></main>;
}
function Trust({ icon: Icon, label }: { icon: React.ElementType; label: string }) { return <div className="flex flex-col items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground"><Icon size={14} className="text-accent" />{label}</div>; }
