# apps/web/Dockerfile — minimal static server for the public verified-clinics dashboard
FROM python:3.11-slim
WORKDIR /web
COPY . .
EXPOSE 8002
CMD ["python", "-m", "http.server", "8002", "--bind", "0.0.0.0"]