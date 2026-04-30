# syntax=docker/dockerfile:1.7
#
# Tuki-Medic frontend — Next.js 16 standalone production image.
#
# Build context: project root.   Build:   docker build -f frontend/Dockerfile -t tuki-medic-frontend:latest .
# Run with the rest of the stack: docker compose up frontend
#
# 3 stages:
#   1. deps    — installs node_modules with the lockfile only (cacheable)
#   2. builder — runs `next build` and produces .next/standalone
#   3. runner  — minimal alpine image, copies .next/standalone + .next/static + public
#
# Configuration: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL must be passed as
# build-args (they are baked into the bundle), then again at runtime as env.

ARG NODE_VERSION=22-alpine

# ---------------------------------------------------------------------------
# 1. deps — install all node_modules
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS deps
WORKDIR /app

# Optional native build deps for any packages that compile on install.
RUN apk add --no-cache libc6-compat

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

# ---------------------------------------------------------------------------
# 2. builder — produce the standalone bundle
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL} \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./

RUN npm run build

# ---------------------------------------------------------------------------
# 3. runner — minimal runtime image
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION} AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root user — Alpine convention.
RUN addgroup -S medagent -g 1001 && adduser -S medagent -G medagent -u 1001

# Copy the standalone bundle (server.js + a minimal node_modules subset)
# plus the static assets and the /public directory.
COPY --from=builder --chown=medagent:medagent /app/.next/standalone ./
COPY --from=builder --chown=medagent:medagent /app/.next/static ./.next/static
COPY --from=builder --chown=medagent:medagent /app/public ./public

USER medagent

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/login || exit 1

CMD ["node", "server.js"]
