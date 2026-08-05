# Stage 1: Build the React application
FROM node:18-alpine AS build

WORKDIR /app

# Copy root and frontend package files
COPY package*.json ./
COPY frontend/package*.json ./frontend/

# Install dependencies
RUN cd frontend && npm install

# Copy source code
COPY . ./

# Build application
RUN npm run build || (cd frontend && npm run build)

# Ensure dist exists at /app/dist
RUN mkdir -p /app/dist && if [ -d "frontend/dist" ]; then cp -r frontend/dist/* /app/dist/ ; fi

# Stage 2: Serve application with Nginx
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
