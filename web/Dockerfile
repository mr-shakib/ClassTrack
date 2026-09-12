# syntax=docker/dockerfile:1
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app

# Next.js compiles rewrites at build time, so the API origin has to be known
# here. The compose service name is the right default for a container run;
# behind Caddy the rewrite never fires anyway.
ARG API_ORIGIN=http://api:8000
ENV API_ORIGIN=$API_ORIGIN

COPY --from=deps /app/node_modules ./node_modules
COPY . .
# `output: "standalone"` in next.config.ts emits a self-contained server bundle,
# so the runtime image needs neither node_modules nor the sources.
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -g 10001 nodejs && adduser -u 10001 -G nodejs -S nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD node -e "require('http').get('http://127.0.0.1:3000/login',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
