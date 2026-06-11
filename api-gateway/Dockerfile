FROM nginx:1.27-alpine

COPY nginx.config /etc/nginx/conf.d/default.conf

EXPOSE 8000

CMD ["nginx", "-g", "daemon off;"]