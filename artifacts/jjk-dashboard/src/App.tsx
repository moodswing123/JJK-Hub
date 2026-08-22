import { useEffect } from 'react';
import { Route, Router as WouterRouter, Switch } from 'wouter';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { setAuthTokenGetter, setBaseUrl } from '@workspace/api-client-react/custom-fetch';
import { Shell } from '@/components/layout/Shell';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Characters from '@/pages/Characters';
import Profile from '@/pages/Profile';
import Shop from '@/pages/Shop';
import Inventory from '@/pages/Inventory';
import Leaderboard from '@/pages/Leaderboard';
import Casino from '@/pages/Casino';
import Marketplace from '@/pages/Marketplace';
import Daily from '@/pages/Daily';
import Transactions from '@/pages/Transactions';
import Admin from '@/pages/Admin';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center text-center">
      <p className="section-label mb-3">Cursed technique unavailable</p>
      <h1 className="mb-3 text-4xl font-semibold">404</h1>
      <p className="text-muted-foreground">This route has not been registered in the realm.</p>
    </div>
  );
}

function Routes() {
  return (
    <Shell>
      <Switch>
        <Route path="/" component={Login} />
        <Route path="/dashboard" component={Dashboard} />
        <Route path="/profile" component={Profile} />
        <Route path="/characters" component={Characters} />
        <Route path="/inventory" component={Inventory} />
        <Route path="/shop" component={Shop} />
        <Route path="/marketplace" component={Marketplace} />
        <Route path="/casino" component={Casino} />
        <Route path="/leaderboard" component={Leaderboard} />
        <Route path="/daily" component={Daily} />
        <Route path="/transactions" component={Transactions} />
        <Route path="/admin" component={Admin} />
        <Route component={NotFound} />
      </Switch>
    </Shell>
  );
}

export default function App() {
  useEffect(() => {
    setBaseUrl(import.meta.env.VITE_API_BASE_URL?.trim() || null);
    setAuthTokenGetter(() => localStorage.getItem('jjk_token'));
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Routes />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
