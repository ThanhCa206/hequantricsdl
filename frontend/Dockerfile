# ==============================================================================
# BenchLab Frontend Dockerfile
# Multi-stage build with Node.js and Nginx
# ==============================================================================

FROM node:22-alpine AS builder

WORKDIR /app

# In Phase 1, placeholder files allow building the image cleanly
COPY frontend/package*.json ./
RUN if [ -f package.json ]; then npm install; fi

COPY frontend ./
RUN if [ -f package.json ]; then npm run build; else mkdir -p dist && echo "<h1>BenchLab Dashboard Ready</h1>" > dist/index.html; fi

FROM nginx:1.27-alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
