FROM node:22-alpine
WORKDIR /workspace
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build && chown -R node:node /workspace
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
