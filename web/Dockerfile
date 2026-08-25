FROM node:24-alpine AS build
WORKDIR /web
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /web
RUN npm install -g serve
COPY --from=build /web/dist ./dist
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
