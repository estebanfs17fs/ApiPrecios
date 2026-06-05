FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY setup.py requirements.txt ./
COPY precios_uy/ precios_uy/

RUN pip install --no-cache-dir --user .


FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "precios_uy.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
