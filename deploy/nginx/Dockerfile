FROM node:20-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json /frontend/package.json
RUN npm install
COPY frontend /frontend
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

