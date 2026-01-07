# React Router v7 SSR Dockerfile
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
# Remove package-lock.json first to fix npm optional dependencies bug
# This ensures Rollup's optional native modules are installed correctly
RUN rm -f package-lock.json 2>/dev/null || true
RUN npm install --legacy-peer-deps

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Build-time Vite env overrides (baked into client bundle)
ARG VITE_API_BASE_URL
ARG VITE_USE_JSONP
ARG VITE_WMS_BASE_URL
ARG VITE_ENFORCE_HTTPS
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_USE_JSONP=${VITE_USE_JSONP}
ENV VITE_WMS_BASE_URL=${VITE_WMS_BASE_URL}
ENV VITE_ENFORCE_HTTPS=${VITE_ENFORCE_HTTPS}

# Build the application
RUN npm run build

# Production image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

# Copy built application
COPY --from=builder /app/build ./build
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./

# Copy only production dependencies
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
ENV PORT=3000

# Start the React Router v7 server
CMD ["npm", "start"]
