FROM node:24-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY db ./db
COPY srv ./srv

ENV NODE_ENV=production
EXPOSE 4004

CMD ["npx", "cds-serve"]
