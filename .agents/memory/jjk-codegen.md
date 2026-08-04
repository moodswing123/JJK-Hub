---
name: JJK Codegen Fix
description: Orval v8 generates Zod v4 syntax (zod.int()) but project uses Zod v3. The codegen script must post-process.
---

## Problem

- Project uses `zod: ^3.25.76` (Zod v3) in pnpm catalog
- Orval v8.23.0 generates `zod.int()` for nullable number fields (Zod v4 syntax)
- Zod v3 has no `zod.int()` — it's `zod.number().int()`

## Fix

Two parts applied:
1. Changed all `type: integer` → `type: number` in `lib/api-spec/openapi.yaml`
2. Added sed post-process to `lib/api-spec/package.json` codegen script:
   ```
   "codegen": "orval --config ./orval.config.ts && sed -i 's/zod\\.int()/zod.number()/g' ../../lib/api-zod/src/generated/api.ts && pnpm -w run typecheck:libs"
   ```

**Why:** Upgrading Zod to v4 would break other things. Downgrading Orval would lose features. The sed post-process is stable and runs after every codegen.

## How to Apply

Any time `pnpm --filter @workspace/api-spec run codegen` is run, the sed fix runs automatically.
If you manually edit the generated file, don't add `zod.int()` — use `zod.number()` instead.
