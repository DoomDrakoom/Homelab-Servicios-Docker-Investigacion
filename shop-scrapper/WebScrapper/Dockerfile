FROM python:3.12-slim

WORKDIR /app

# Dependencias Python + Chromium para los scrapers que renderizan JS (Aldi)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY scraper/ scraper/
COPY app/ app/

# Datos persistentes (caché de scrapes, Excel generados, historial de jobs)
VOLUME /app/data

EXPOSE 8000
ENV LOG_LEVEL=INFO

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
