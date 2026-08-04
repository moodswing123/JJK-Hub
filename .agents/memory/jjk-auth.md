---
name: JJK Auth Pattern
description: How authentication works in the JJK dashboard — JWT in localStorage, Shell auth guard, Login page pattern.
---

## Auth Flow

1. User hits Telegram Login Widget → callback fires with Telegram data
2. `useTelegramLogin.mutateAsync({ data: telegramData })` → POST `/api/auth/telegram`
3. Server verifies Telegram hash, upserts player, returns `{ token, player }`
4. Token stored in `localStorage.setItem('jjk_token', token)`
5. `setAuthTokenGetter(() => token)` → all future API calls include `Authorization: Bearer <token>`
6. Redirect to `/dashboard`

## Shell Auth Guard

- `Shell` component: if `location === '/'`, render `<>{children}</>` directly (no auth check)
- For all other routes, render `AuthenticatedShell` which calls `useGetMe`
- If `isError || !me`, render `<Redirect to="/" />`

## Login Page Rule

**NEVER call `useGetMe` in Login.tsx** — it causes a request loop.
Login only checks `localStorage.getItem('jjk_token')` to auto-redirect if already logged in.

**Why:** `useGetMe` without a token returns 401, and even with `retry: false`, the React Query `refetchOnWindowFocus` (or React StrictMode double-effect) causes hundreds of requests per second in a loop.

## QueryClient Defaults

Always set globally in App.tsx:
```javascript
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
```

## Telegram Widget in Dev

The `data-telegram-login` attribute must match the bot's username registered with BotFather. The widget shows "Bot domain invalid" on localhost/dev domains — this is expected. It only works on the deployed domain registered with BotFather.
