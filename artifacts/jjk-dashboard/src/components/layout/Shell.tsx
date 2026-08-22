import React from 'react';
import { useLocation, Link, Redirect } from 'wouter';
import { useGetMe, useLogout, useListNotifications, getListNotificationsQueryKey, getGetMeQueryKey } from '@workspace/api-client-react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Home, Users, ShoppingCart, Briefcase, Trophy, Coins, 
  Store, Calendar, History, Shield, User, LogOut, Bell,
  Menu, X
} from 'lucide-react';
import { Button } from '@/components/ui/core';

export function Shell({ children }: { children: React.ReactNode }) {
  const [location, setLocation] = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const isLoginPage = location === '/';

  // On the login page, just render children directly (no auth needed)
  if (isLoginPage) {
    return <>{children}</>;
  }

  return <AuthenticatedShell onLocation={setLocation} location={location} mobileMenuOpen={mobileMenuOpen} setMobileMenuOpen={setMobileMenuOpen}>{children}</AuthenticatedShell>;
}

function AuthenticatedShell({
  children,
  location,
  onLocation,
  mobileMenuOpen,
  setMobileMenuOpen,
}: {
  children: React.ReactNode;
  location: string;
  onLocation: (l: string) => void;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: (v: boolean) => void;
}) {
  const { data: me, isLoading, isError } = useGetMe({ query: { queryKey: getGetMeQueryKey(), retry: false, staleTime: 30_000 } });
  const logout = useLogout();
  const { data: notifications } = useListNotifications({ query: { staleTime: 60_000, queryKey: getListNotificationsQueryKey() } });
  const unreadCount = notifications?.filter(n => !n.read).length ?? 0;

  // Redirect to login if not authenticated
  if (!isLoading && (isError || !me)) {
    return <Redirect to="/" />;
  }

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: Home },
    { name: 'Profile', path: '/profile', icon: User },
    { name: 'Characters', path: '/characters', icon: Users },
    { name: 'Inventory', path: '/inventory', icon: Briefcase },
    { name: 'Shop', path: '/shop', icon: ShoppingCart },
    { name: 'Marketplace', path: '/marketplace', icon: Store },
    { name: 'Casino', path: '/casino', icon: Coins },
    { name: 'Leaderboard', path: '/leaderboard', icon: Trophy },
    { name: 'Daily', path: '/daily', icon: Calendar },
    { name: 'History', path: '/transactions', icon: History },
  ];

  if (me?.is_admin) {
    navItems.push({ name: 'Admin', path: '/admin', icon: Shield });
  }

  const handleLogout = async () => {
    try { await logout.mutateAsync(undefined); } catch {}
    localStorage.removeItem('jjk_token');
    onLocation('/');
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-background text-foreground bg-grid-pattern relative overflow-hidden">
      {/* Background glows */}
      <div className="fixed top-0 left-0 w-[500px] h-[500px] bg-primary/15 rounded-full blur-[130px] pointer-events-none mix-blend-screen -translate-x-1/2 -translate-y-1/2" />
      <div className="fixed bottom-0 right-0 w-[500px] h-[500px] bg-secondary/15 rounded-full blur-[130px] pointer-events-none mix-blend-screen translate-x-1/3 translate-y-1/3" />

      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between p-4 glass border-b border-white/5 sticky top-0 z-50">
        <div className="font-display font-bold text-xl tracking-wider bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
          JJK RPG
        </div>
        <div className="flex items-center gap-4">
          <Link href="/transactions">
            <button className="relative text-muted-foreground hover:text-white transition-colors" data-testid="button-notifications-mobile" aria-label="View notifications and history">
              <Bell size={20} />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-primary rounded-full text-[10px] flex items-center justify-center text-white font-bold">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
          </Link>
          <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="text-white" data-testid="button-mobile-menu">
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* Sidebar */}
      <AnimatePresence>
        {(mobileMenuOpen) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 md:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}
      </AnimatePresence>

      <aside className={`fixed md:sticky top-0 left-0 z-40 h-dvh w-64 glass border-r border-white/5 flex flex-col transition-transform duration-300 ease-in-out ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0`}>
        {/* Logo */}
        <div className="p-6 hidden md:flex flex-col">
          <div className="font-display font-bold text-2xl tracking-widest bg-gradient-to-r from-primary via-accent to-secondary bg-clip-text text-transparent text-glow">
            JJK RPG
          </div>
          <div className="text-xs text-muted-foreground mt-1 tracking-widest uppercase font-mono">Sorcerer Interface</div>
        </div>

        {/* Player mini card */}
        {me && (
          <div className="px-4 pb-4">
            <Link href="/profile">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/10 cursor-pointer hover:bg-white/10 transition-colors" data-testid="link-profile-mini">
                <div className="w-10 h-10 rounded-full overflow-hidden bg-muted flex-shrink-0">
                  {me.avatar_url ? (
                    <img src={me.avatar_url} alt={me.display_name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-primary/20 text-primary font-bold text-sm">
                      {me.display_name?.charAt(0) ?? '?'}
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold truncate">{me.display_name}</div>
                  <div className="text-xs text-muted-foreground truncate">{me.rank}</div>
                </div>
              </div>
            </Link>
          </div>
        )}

        {/* Loading skeleton for player card */}
        {isLoading && (
          <div className="px-4 pb-4">
            <div className="h-16 rounded-lg bg-white/5 animate-pulse" />
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 px-4 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = location === item.path || location.startsWith(`${item.path}/`);
            const Icon = item.icon;
            return (
              <Link href={item.path} key={item.path} onClick={() => setMobileMenuOpen(false)}>
                <div
                  data-testid={`link-nav-${item.name.toLowerCase()}`}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200 ${
                    isActive
                      ? 'bg-primary/20 text-primary shadow-[inset_2px_0_0_0_hsl(var(--primary))]'
                      : 'text-muted-foreground hover:bg-white/5 hover:text-foreground'
                  }`}
                >
                  <Icon size={18} />
                  <span className="font-medium text-sm tracking-wide">{item.name}</span>
                  {item.name === 'History' && unreadCount > 0 && (
                    <span className="ml-auto w-5 h-5 bg-primary rounded-full text-[10px] flex items-center justify-center text-white font-bold">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="p-4 mt-auto border-t border-white/5">
          <Button
            variant="ghost"
            className="w-full justify-start text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            onClick={handleLogout}
            data-testid="button-logout"
          >
            <LogOut size={18} className="mr-3" />
            Logout
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 h-dvh overflow-y-auto relative z-10 scroll-smooth">
        <div className="max-w-7xl mx-auto p-4 md:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
