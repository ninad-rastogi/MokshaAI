FROM node:24-alpine

WORKDIR /app
RUN chown node:node /app
USER node

COPY --chown=node:node package.json package-lock.json* ./
RUN npm ci --ignore-scripts

COPY --chown=node:node . .
RUN npm run build

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
