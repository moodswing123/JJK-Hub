import React, { useEffect, useRef } from 'react';
import { useLocation } from 'wouter';
import { useTelegramLogin } from '@workspace/api-client-react';
import { setAuthTokenGetter } from '@workspace/api-client-react/custom-fetch';
import { motion } from 'framer-motion';

export default function Login() {
  const [, setLocation] = useLocation();
  const telegramBotUsername = import.meta.env.VITE_TELEGRAM_BOT_USERNAME?.trim();
  const loginMutation = useTelegramLogin();
  const widgetContainer = useRef<HTMLDivElement>(null);

  // If already logged in, redirect immediately
  useEffect(() => {
    const token = localStorage.getItem('jjk_token');
    if (token) {
      setAuthTokenGetter(() => token);
      setLocation('/dashboard');
    }
  }, [setLocation]);

  useEffect(() => {
    if (!widgetContainer.current) return;
    widgetContainer.current.innerHTML = '';
    if (!telegramBotUsername) return;

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute('data-telegram-login', telegramBotUsername);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-radius', '10');
    script.setAttribute('data-request-access', 'write');
    script.setAttribute('data-userpic', 'false');
    script.setAttribute('data-onauth', 'onTelegramAuth(user)');

    (window as any).onTelegramAuth = async (user: any) => {
      try {
        const result = await loginMutation.mutateAsync({ data: user });
        if (result.token) {
          localStorage.setItem('jjk_token', result.token);
          setAuthTokenGetter(() => result.token);
          setLocation('/dashboard');
        }
      } catch (err) {
        console.error('Login failed', err);
      }
    };

    widgetContainer.current.appendChild(script);
    return () => { delete (window as any).onTelegramAuth; };
  }, [loginMutation, setLocation, telegramBotUsername]);

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center relative overflow-hidden bg-grid-pattern">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,0,0,0)_0%,rgba(0,0,0,0.8)_100%)] z-0" />
      <motion.div
        animate={{ scale: [1, 1.05, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/20 rounded-full blur-[150px] mix-blend-screen z-0 pointer-events-none"
      />
      <motion.div
        animate={{ scale: [1, 1.1, 1], opacity: [0.2, 0.4, 0.2] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
        className="absolute top-1/3 right-1/4 w-[600px] h-[600px] bg-secondary/30 rounded-full blur-[120px] mix-blend-screen z-0 pointer-events-none"
      />

      <div className="relative z-10 w-full max-w-md p-8 flex flex-col items-center">
        <motion.div
          initial={{ y: -50, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="text-center mb-12"
        >
          <h1 className="font-display font-black text-6xl md:text-8xl tracking-tighter bg-gradient-to-b from-white via-white to-white/40 bg-clip-text text-transparent text-glow mb-4">
            JJK RPG
          </h1>
          <p className="text-muted-foreground tracking-[0.3em] uppercase text-sm font-semibold font-mono">
            Sorcerer Interface System
          </p>
        </motion.div>

        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.4 }}
          className="glass-card w-full p-8 flex flex-col items-center relative overflow-hidden"
        >
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-primary to-transparent" />

          <h2 className="text-xl font-display font-bold mb-2 text-center">Authenticate to Continue</h2>
          <p className="text-sm text-muted-foreground mb-8 text-center">Connect your Telegram account to enter the Jujutsu Kaisen world</p>

          {!telegramBotUsername ? (
            <div className="w-full rounded-lg border border-amber-400/25 bg-amber-400/10 px-4 py-3 text-center text-sm text-amber-200">
              Telegram authentication is not configured for this deployment. Set <code className="font-mono text-xs">VITE_TELEGRAM_BOT_USERNAME</code> to the bot username to enable sign-in.
            </div>
          ) : loginMutation.isPending ? (
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-muted-foreground font-mono">Verifying sorcerer identity...</p>
            </div>
          ) : loginMutation.isError ? (
            <div className="flex flex-col items-center gap-4 py-2 w-full">
              <div className="w-full p-3 rounded-lg bg-destructive/20 border border-destructive/40 text-destructive text-sm text-center">
                Authentication failed. Please try again.
              </div>
              <div ref={widgetContainer} className="min-h-[40px] flex items-center justify-center" />
            </div>
          ) : (
            <div ref={widgetContainer} className="min-h-[40px] flex items-center justify-center" data-testid="container-telegram-widget" />
          )}

          <div className="mt-8 text-xs text-muted-foreground text-center font-mono">
            CONNECTION SECURE // CURSED SEAL ENCRYPTED
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="mt-8 text-center"
        >
          <p className="text-xs text-muted-foreground/50 font-mono">
            Need Yen? Contact{' '}
            <a
              href="https://t.me/victory_tech"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent/80 transition-colors underline underline-offset-2"
              data-testid="link-contact-seller"
            >
              @victory_tech
            </a>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
