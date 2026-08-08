# Stage 1: Build the React application
FROM node:18-alpine AS build

WORKDIR /app

# Copy package manifests from both root and frontend
COPY package*.json ./
COPY frontend/package*.json ./frontend/

# Install dependencies in frontend directory if it exists, otherwise in current directory
RUN if [ -f "frontend/package.json" ]; then cd frontend && npm install; else npm install; fi

# Copy all source files
COPY . ./

# Build the React frontend
RUN if [ -d "frontend" ]; then cd frontend && npm run build; else npm run build; fi

# Ensure /app/dist has the built static files
RUN mkdir -p /app/dist && \
    if [ -d "frontend/dist" ]; then cp -a frontend/dist/. /app/dist/ ; \
    elif [ -d "dist" ]; then cp -a dist/. /app/dist/ ; fi

# Stage 2: Serve application with Nginx
FROM nginx:alpine

# Clean default html
RUN rm -rf /usr/share/nginx/html/* /var/www/html/* /etc/nginx/conf.d/*

# Copy built assets to both standard Nginx directories
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/dist /var/www/html

# Copy custom Nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
