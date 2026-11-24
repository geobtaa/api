FROM node:24-alpine AS base
ARG NPM_VERSION=12.0.2
RUN npm install --global "npm@${NPM_VERSION}"

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS builder
COPY . .
RUN npm run build

FROM nginx:1.30.4-alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
