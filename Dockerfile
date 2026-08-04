# Multi-stage Dockerfile for pnpm workspace (api-server)
# Uses Corepack to enable pnpm and builds only the api-server artifact

FROM node:20-alpine AS deps
WORKDIR /app
# Copy lockfiles and minimal workspace metadata first for deterministic installs
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc ./

# Enable corepack and activate pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Install all workspace dependencies according to lockfile
RUN pnpm install --frozen-lockfile

########################################
FROM node:20-alpine AS build
WORKDIR /app
# Reuse installed deps and copy source
COPY --from=deps /app /app
COPY . .

# Ensure pnpm is available and build the api-server package
RUN corepack enable && corepack prepare pnpm@latest --activate \
    && pnpm -w --filter "@workspace/api-server" run build

########################################
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Install production dependencies only
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json .npmrc ./
RUN corepack enable && corepack prepare pnpm@latest --activate \
    && pnpm install --frozen-lockfile --prod

# Copy built artifact from build stage
COPY --from=build /app/artifacts/api-server/dist ./artifacts/api-server/dist

# Expose default port; Railway provides PORT env at runtime
EXPOSE 3000

# Start the built ESM app (the api-server's start uses dist/index.mjs)
CMD ["node", "--enable-source-maps", "artifacts/api-server/dist/index.mjs"]
