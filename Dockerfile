# Stage 1: Build the React application
FROM node:18-alpine AS build

WORKDIR /app

# Copy package files from frontend or root
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy source code from frontend
COPY frontend/ ./

# Build application
RUN npm run build

# Ensure /app/dist exists for stage 2
RUN mkdir -p /app/dist

# Stage 2: Serve application with Nginx
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
