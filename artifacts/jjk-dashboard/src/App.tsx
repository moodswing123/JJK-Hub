import React, { useEffect } from 'react';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { setAuthTokenGetter } from '@workspace/api-client-react/custom-fetch';

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

const NotFound = () => <div className="p-8 text-center text-xl text-muted-foreground h-full flex items-center justify-center font-display">404 - Domain Expansion Failed</div>;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      staleTime: 30_000,
    },
  },
});

function Router() {
  return (
    <Shell>
      <Switch>
        <Route path="/" component={Login} />
        <Route path="/dashboard" component={Dashboard} />
        <Route path="/profile" component={Profile} />
        <Route path="/characters" component={Characters} />
        <Route path="/shop" component={Shop} />
        <Route path="/inventory" component={Inventory} />
        <Route path="/leaderboard" component={Leaderboard} />
        <Route path="/casino" component={Casino} />
        <Route path="/marketplace" component={Marketplace} />
        <Route path="/daily" component={Daily} />
        <Route path="/transactions" component={Transactions} />
        <Route path="/admin" component={Admin} />
        <Route component={NotFound} />
      </Switch>
    </Shell>
  );
}

function App() {
  useEffect(() => {
    setAuthTokenGetter(() => localStorage.getItem("jjk_token"));
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
