FROM node:22-alpine AS dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG SITE_URL=https://qianscope.zeabur.app
ARG NEXT_PUBLIC_SITE_URL=https://qianscope.zeabur.app
ARG NEXT_PUBLIC_AMAP_KEY
ARG NEXT_PUBLIC_AMAP_SECURITY_JS_CODE
ARG NEXT_PUBLIC_AMAP_STYLE=amap://styles/whitesmoke
ENV SITE_URL=${SITE_URL}
ENV NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL}
ENV NEXT_PUBLIC_AMAP_KEY=${NEXT_PUBLIC_AMAP_KEY}
ENV NEXT_PUBLIC_AMAP_SECURITY_JS_CODE=${NEXT_PUBLIC_AMAP_SECURITY_JS_CODE}
ENV NEXT_PUBLIC_AMAP_STYLE=${NEXT_PUBLIC_AMAP_STYLE}
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=8080
COPY --from=builder --chown=node:node /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 8080
CMD ["node", "server.js"]
