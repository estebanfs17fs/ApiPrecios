FROM python:3.11-slim

WORKDIR /app

COPY setup.py pyproject.toml ./
COPY precios_uy/ precios_uy/

RUN pip install --no-cache-dir . \
    # Chromium + dependencias del sistema para scrapear Disco y Devoto (scroll infinito)
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "precios_uy.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
