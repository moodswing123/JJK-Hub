# Multi-stage Dockerfile for pnpm workspace (api-server)
# Uses Corepack to enable pnpm and builds only the api-server artifact
# Uses Debian slim base to avoid musl/native binary issues and installs build tools

# -------------------- deps stage --------------------
FROM node:22-bullseye-slim AS deps
WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

# Install build tools needed for native module builds (esbuild, node-gyp, etc.)
RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 build-essential ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Copy lockfiles and minimal workspace metadata first for deterministic installs
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc ./

# Activate pnpm and print its version for debugging
RUN corepack enable \
  && corepack prepare pnpm@latest --activate \
  && pnpm --version || true

# Approve build scripts non-interactively; if the active pnpm doesn't provide the command, install pnpm globally and retry
RUN pnpm approve-builds --all --yes || (npm i -g pnpm@latest && pnpm approve-builds --all --yes)

# Install workspace deps from lockfile (no --approve-builds flag here)
RUN pnpm install --frozen-lockfile

# -------------------- build stage --------------------
FROM node:22-bullseye-slim AS build
WORKDIR /app
# Reuse installed deps and copy source
COPY --from=deps /app /app
COPY . .

# Ensure pnpm is available and build the api-server package
RUN corepack enable \
  && corepack prepare pnpm@latest --activate \
  && pnpm -w --filter "@workspace/api-server" run build

# -------------------- runner stage --------------------
FROM node:22-bullseye-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV DEBIAN_FRONTEND=noninteractive

# Copy package metadata
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc ./

# Copy node_modules and pnpm store from deps stage to avoid re-running pnpm in the runner
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/.pnpm-store ./.pnpm-store || true

# Copy built artifact from build stage
COPY --from=build /app/artifacts/api-server/dist ./artifacts/api-server/dist

# Expose default port; Railway provides PORT env at runtime
EXPOSE 3000

# Start the built ESM app (the api-server's start uses dist/index.mjs)
CMD ["node", "--enable-source-maps", "artifacts/api-server/dist/index.mjs"]
