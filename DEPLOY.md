# Guía de Producción — Precios UY

> Pasos para poner la API en producción usando Docker.

---

## Requisitos

- **Servidor Linux** (Ubuntu 22.04+ recomendado)
- **Docker** y **Docker Compose** instalados
- **Dominio** (opcional, para HTTPS)
- **GitHub** (para CI/CD y Container Registry)

---

## 1. Despliegue rápido con Docker Compose

```bash
# Clonar el repositorio
git clone https://github.com/estebanfs17fs/ApiPrecios.git
cd ApiPrecios

# Configurar variables de entorno
cp .env.example .env
# Editar .env según necesidad
nano .env

# Iniciar el servicio
docker compose up -d

# Ver logs
docker compose logs -f

# Verificar que funciona
curl http://localhost:8000/api/supermercados
```

La API queda disponible en `http://localhost:8000`.

Documentación interactiva:
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 2. Variables de Entorno

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:////app/data/precios_uy.db` | Conexión a BD |
| `API_HOST` | `0.0.0.0` | Host del servidor |
| `API_PORT` | `8000` | Puerto del servidor |
| `REQUEST_TIMEOUT` | `30` | Timeout HTTP (segundos) |
| `SCRAP_INTERVAL_HOURS` | `6` | Intervalo scraping automático |
| `CACHE_TTL_HOURS` | `6` | Duración del caché |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `LOG_FILE` | `precios_uy.log` | Archivo de log |

---

## 3. Usando PostgreSQL (recomendado para producción)

SQLite funciona bien, pero PostgreSQL es más robusto para múltiples accesos concurrentes.

### docker-compose.yml con PostgreSQL

```yaml
version: "3.9"

services:
  api:
    build: .
    container_name: precios-uy-api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://precios:precios@db:5432/precios_uy
      - LOG_LEVEL=INFO
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    container_name: precios-uy-db
    environment:
      - POSTGRES_USER=precios
      - POSTGRES_PASSWORD=precios
      - POSTGRES_DB=precios_uy
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U precios"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  pg_data:
```

**Importante:** Cambiar la contraseña en producción.

---

## 4. Nginx + HTTPS (con certificado SSL)

### docker-compose.yml con Nginx

```yaml
services:
  api:
    build: .
    container_name: precios-uy-api
    expose:
      - "8000"
    environment:
      - DATABASE_URL=sqlite:////app/data/precios_uy.db
    volumes:
      - api_data:/app/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: precios-uy-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  api_data:
```

### nginx.conf

```nginx
upstream api {
    server api:8000;
}

server {
    listen 80;
    server_name api.midominio.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name api.midominio.com;

    ssl_certificate /etc/letsencrypt/live/api.midominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.midominio.com/privkey.pem;

    location / {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Obtener certificado SSL

```bash
# Instalar certbot
sudo apt install certbot

# Obtener certificado
sudo certbot certonly --standalone -d api.midominio.com

# Renovación automática (certbot crea un timer)
sudo systemctl status certbot.timer
```

---

## 5. Despliegue con GitHub Actions

El CI/CD ya está configurado en `.github/workflows/`:

| Workflow | Disparador | Qué hace |
|---|---|---|
| `ci.yml` | Push/PR a `main` | Ejecuta tests en Python 3.10, 3.11, 3.12 + lint con ruff |
| `docker.yml` | Push a `main` o tags `v*` | Construye imagen Docker y la publica en `ghcr.io` |

### Pasos para activar Docker CD:

1. Ir a GitHub → Settings → Actions → General → **Workflow permissions**
2. Habilitar **Read and write permissions**
3. En el repositorio, ir a **Actions** y aceptar los workflows

Luego de pushear a `main`, la imagen queda disponible en:

```
ghcr.io/estebanfs17fs/apiprecios:latest
```

### Desplegar desde GitHub Container Registry en el servidor:

```bash
docker pull ghcr.io/estebanfs17fs/apiprecios:latest
docker run -d \
  --name precios-uy \
  -p 8000:8000 \
  -v api_data:/app/data \
  -e DATABASE_URL=sqlite:////app/data/precios_uy.db \
  ghcr.io/estebanfs17fs/apiprecios:latest
```

O con docker-compose usando la imagen pre-construida:

```yaml
services:
  api:
    image: ghcr.io/estebanfs17fs/apiprecios:latest
    container_name: precios-uy-api
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - api_data:/app/data
    restart: unless-stopped

volumes:
  api_data:
```

---

## 6. Scraping inicial

```bash
# Ejecutar scraping manual una vez
docker compose exec api python3 -m precios_uy scrapear

# Programar scraping automático
docker compose exec api python3 -m precios_uy schedule
```

---

## 7. Monitoreo

```bash
# Ver logs en tiempo real
docker compose logs -f

# Ver estado del contenedor
docker compose ps

# Ver uso de recursos
docker stats precios-uy-api
```

---

## 8. Respaldo de datos

```bash
# Respaldar SQLite
docker run --rm -v api_data:/data -v $(pwd):/backup alpine \
  cp /data/precios_uy.db /backup/backup-$(date +%Y%m%d).db

# Restaurar
docker run --rm -v api_data:/data -v $(pwd):/backup alpine \
  cp /backup/precios_uy.db /data/precios_uy.db
```

---

## 9. Actualización

```bash
cd /opt/ApiPrecios
git pull
docker compose down
docker compose up -d --build
curl http://localhost:8000/api/supermercados
```
