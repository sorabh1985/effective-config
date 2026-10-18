FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py config.development.yaml .env ./

# OS-level environment layer (APP_* prefix)
ENV APP_PORT=8188 \
    APP_WORKERS=2 \
    APP_DEBUG=true \
    APP_LOG_LEVEL=error \
    APP_API_KEY=key-lt45g8x3px \
    CONFIG_ENV=development

EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
