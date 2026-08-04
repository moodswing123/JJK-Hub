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

# Enable corepack and activate pnpm, then install workspace deps allowing required build scripts
RUN corepack enable \
  && corepack prepare pnpm@latest --activate \
  && pnpm install --approve-builds --frozen-lockfile

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

# Install only production dependencies (approve build scripts non-interactively)
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc ./
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/* \
  && corepack enable \
  && corepack prepare pnpm@latest --activate \
  && pnpm install --approve-builds --frozen-lockfile --prod

# Copy built artifact from build stage
COPY --from=build /app/artifacts/api-server/dist ./artifacts/api-server/dist

# Expose default port; Railway provides PORT env at runtime
EXPOSE 3000

# Start the built ESM app (the api-server's start uses dist/index.mjs)
CMD ["node", "--enable-source-maps", "artifacts/api-server/dist/index.mjs"]
