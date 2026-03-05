FROM node:20.20.0-alpine@sha256:09e2b3d9726018aecf269bd35325f46bf75046a643a66d28360ec71132750ec8

WORKDIR /app

ARG VITE_API_BASE=http://localhost:8081
ENV VITE_API_BASE=${VITE_API_BASE}

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
RUN npm run build

EXPOSE 8082
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8082"]
