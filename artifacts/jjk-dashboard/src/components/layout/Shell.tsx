import React from 'react';
import { Link, Redirect, useLocation } from 'wouter';
import { motion, AnimatePresence } from 'framer-motion';
import { useGetMe, useLogout, useListNotifications, getGetMeQueryKey, getListNotificationsQueryKey } from '@workspace/api-client-react';
import { Bell, BookOpen, BriefcaseBusiness, CalendarDays, ChevronRight, Coins, Compass, Crown, Gamepad2, LayoutDashboard, LogOut, Menu, Package, Shield, ShoppingBag, Swords, Trophy, UserRound, X } from 'lucide-react';
import { Button } from '@/components/ui/core';

const navItems = [
  { label: 'Overview', path: '/dashboard', icon: LayoutDashboard },
  { label: 'My profile', path: '/profile', icon: UserRound },
  { label: 'Characters', path: '/characters', icon: Swords },
  { label: 'Inventory', path: '/inventory', icon: Package },
  { label: 'Daily missions', path: '/daily', icon: CalendarDays },
  { label: 'Leaderboard', path: '/leaderboard', icon: Trophy },
  { label: 'Marketplace', path: '/marketplace', icon: Compass },
  { label: 'Cursed casino', path: '/casino', icon: Coins },
  { label: 'Shop', path: '/shop', icon: ShoppingBag },
  { label: 'Transactions', path: '/transactions', icon: BookOpen },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useLocation();
  const [open, setOpen] = React.useState(false);
  const { data: me, isLoading, isError } = useGetMe({ query: { queryKey: getGetMeQueryKey(), retry: false } });
  const { data: notifications } = useListNotifications({ query: { queryKey: getListNotificationsQueryKey(), staleTime: 60_000 } });
  const logout = useLogout();
  const notificationList = Array.isArray(notifications) ? notifications : [];
  const unread = notificationList.filter((notification) => !notification.read).length;

  if (location === '/') return <>{children}</>;
  if (!isLoading && (isError || !me)) return <Redirect to="/" />;

  const items = me?.is_admin ? [...navItems, { label: 'Admin', path: '/admin', icon: Shield }] : navItems;
  const closeMenu = () => setOpen(false);
  const handleLogout = async () => {
    try { await logout.mutateAsync(undefined); } catch { /* token cleanup still matters */ }
    localStorage.removeItem('jjk_token');
    setLocation('/');
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-[34rem] w-[34rem] rounded-full bg-primary/10 blur-[130px]" />
        <div className="absolute -bottom-48 -right-32 h-[30rem] w-[30rem] rounded-full bg-accent/8 blur-[140px]" />
      </div>
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur-xl lg:hidden">
        <div className="flex h-16 items-center justify-between px-4">
          <Brand compact />
          <div className="flex items-center gap-2">
            <Link href="/transactions"><Button variant="ghost" size="icon" className="relative" aria-label="Open transaction history"><Bell size={18} />{unread > 0 && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />}</Button></Link>
            <Button variant="ghost" size="icon" onClick={() => setOpen((value) => !value)} aria-label="Toggle navigation">{open ? <X size={20} /> : <Menu size={20} />}</Button>
          </div>
        </div>
      </header>
      <AnimatePresence>{open && <motion.button aria-label="Close navigation" className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden" onClick={closeMenu} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />}</AnimatePresence>
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[17.5rem] flex-col border-r border-border/80 bg-card/95 backdrop-blur-2xl transition-transform duration-200 lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex h-20 items-center border-b border-border/70 px-6"><Brand /></div>
        <div className="border-b border-border/70 px-4 py-4">
          {me ? <Link href="/profile" onClick={closeMenu}><div className="group flex items-center gap-3 rounded-xl border border-border/70 bg-background/50 p-3 transition-colors hover:border-primary/40 hover:bg-primary/5"><Avatar player={me} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{me.display_name}</p><p className="truncate text-xs text-muted-foreground">{me.rank} · Level {me.level}</p></div><ChevronRight size={15} className="text-muted-foreground transition-transform group-hover:translate-x-0.5" /></div></Link> : <div className="h-14 animate-pulse rounded-xl bg-muted/50" />}
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-5">
          <p className="section-label mb-3 px-3">Command center</p>
          {items.map(({ label, path, icon: Icon }) => { const active = location === path || location.startsWith(`${path}/`); return <Link key={path} href={path} onClick={closeMenu}><div className={`group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all ${active ? 'bg-primary/12 text-foreground shadow-[inset_2px_0_0_hsl(var(--primary))]' : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'}`}><Icon size={17} className={active ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'} /><span className="flex-1">{label}</span>{label === 'Transactions' && unread > 0 && <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground">{unread > 9 ? '9+' : unread}</span>}</div></Link>; })}
        </nav>
        <div className="border-t border-border/70 p-4"><Button variant="ghost" className="w-full justify-start gap-3 text-muted-foreground hover:bg-destructive/10 hover:text-destructive" onClick={handleLogout}><LogOut size={17} /> Sign out</Button></div>
      </aside>
      <main className="relative min-h-screen lg:pl-[17.5rem]"><div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-10 lg:py-9">{children}</div></main>
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) { return <Link href="/dashboard"><div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/20"><Gamepad2 size={18} /></div><div className={compact ? 'block' : 'block'}><p className="font-display text-base font-semibold tracking-tight">Cursed Realm</p><p className="section-label !text-[9px]">JJK RPG command center</p></div></div></Link>; }
function Avatar({ player }: { player: { avatar_url?: string | null; display_name?: string | null } }) { return <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-primary/30 bg-primary/10 text-sm font-semibold text-primary">{player.avatar_url ? <img src={player.avatar_url} alt="" className="h-full w-full object-cover" /> : player.display_name?.charAt(0).toUpperCase() || <Crown size={16} />}</div>; }
