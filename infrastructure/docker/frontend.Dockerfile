# Base Node 24 Alpine image for lightweight build
FROM node:24-alpine

WORKDIR /app

# Copy package configurations and install packages
COPY package*.json ./
RUN npm install

# Copy frontend source files
COPY . .

# Build-time argument for API backend routing (e.g. /api or custom port)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Compile the application for production deployment
RUN npm run build

# Expose Next.js runtime port
EXPOSE 3000

# Start Next.js server in production mode
CMD ["npm", "run", "start"]
