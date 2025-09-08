FROM node:20-alpine

WORKDIR /app

ARG VITE_API_BASE=http://localhost:8081
ENV VITE_API_BASE=${VITE_API_BASE}

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY . .
RUN npm run build

EXPOSE 8082
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "8082"]
