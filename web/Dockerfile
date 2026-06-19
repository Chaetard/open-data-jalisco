# syntax=docker/dockerfile:1
# Build estático del SPA (Vite/React) servido por Caddy. Caddy además hace de
# reverse proxy: /api/* -> contenedor `api`. El front pega a `/api` de forma
# relativa, así que NO necesita saber la URL del backend (cero config de front).

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
