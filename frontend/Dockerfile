FROM nginx:1.28-alpine
ENV PORT=80 CORE_UPSTREAM=core:8000 NOTIFICATIONS_UPSTREAM=notifications:5000 REPORTS_UPSTREAM=reports:5001
COPY frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY frontend/index.html frontend/app.js frontend/styles.css frontend/base.css frontend/favicon.svg /usr/share/nginx/html/
EXPOSE 80
