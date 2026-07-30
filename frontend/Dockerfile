FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# .env is tracked in this private repo — Next.js loads it automatically during
# build (NEXT_PUBLIC_* inlining + next.config.mjs env/rewrites resolution).
# ARGs with defaults match production so the build always gets the right values
# even if docker compose doesn't pass --build-arg.
ARG BACKEND_INTERNAL_URL=http://10.2.8.73:8025
ARG NEXT_PUBLIC_API_URL=https://canvas.iiit.ac.in/taxsyncbestage
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY . .
RUN rm -rf .next && npm run build && test -f .next/standalone/server.js

# Production
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8026
ENV HOSTNAME="0.0.0.0"

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# Prefix-restoring entrypoint: re-adds the /taxsyncfestage that campus nginx
# strips, so the basePath build serves correctly with no nginx change.
COPY --from=builder /app/entry.js ./entry.js

# Copy public folder if it exists (optional assets)
COPY --from=builder /app/public ./public

RUN chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 8026

CMD ["node", "entry.js"]
