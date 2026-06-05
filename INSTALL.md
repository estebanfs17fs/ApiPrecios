# Manual de Instalación — Precios UY

---

## Requisitos

- **Python** 3.10 o superior
- **pip** (gestor de paquetes de Python)
- **git** (para clonar el repositorio)
- **Conexión a internet** (para instalar dependencias y ejecutar scrapers)

---

## Instalación paso a paso

### 1. Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd precios_uy
```

### 2. Crear y activar entorno virtual (recomendado)

```bash
python3 -m venv venv
source venv/bin/activate   # Linux / macOS
# venv\Scripts\activate    # Windows
```

### 3. Instalar el paquete y dependencias

```bash
pip install -e .
```

Esto instala:
- `fastapi` + `uvicorn` — Servidor web
- `sqlalchemy` — ORM para base de datos
- `beautifulsoup4` + `lxml` — Parsing HTML
- `cloudscraper` — Bypass Cloudflare
- `click` — CLI
- `apscheduler` — Scraping automático
- `pydantic-settings` — Configuración

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` si es necesario:

```env
DATABASE_URL=sqlite:///precios_uy.db
SCRAP_INTERVAL_HOURS=6
API_HOST=0.0.0.0
API_PORT=8000
REQUEST_TIMEOUT=30
```

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite:///precios_uy.db` | URL de conexión a BD |
| `SCRAP_INTERVAL_HOURS` | `6` | Intervalo de scraping automático |
| `API_HOST` | `0.0.0.0` | Host del servidor API |
| `API_PORT` | `8000` | Puerto del servidor API |
| `REQUEST_TIMEOUT` | `30` | Timeout para requests HTTP |

### 5. Verificar instalación

```bash
python3 -m precios_uy supermercados
# Debería mostrar: No hay datos. Ejecutá 'scrapear' para poblar la base de datos.
```

### 6. (Opcional) Instalar dependencias de test

```bash
pip install pytest httpx pytest-cov
```

---

## Ejecución

### CLI

```bash
# Scrapear todos los supermercados
precios-uy scrapear

# Ver productos
precios-uy listar
precios-uy buscar "leche"
precios-uy supermercados

# Scraping automático
precios-uy schedule
```

Si `precios-uy` no está en PATH:

```bash
python3 -m precios_uy scrapear
```

### API REST

```bash
python3 run_api.py
# Servidor en http://0.0.0.0:8000
# Docs: http://localhost:8000/docs
```

### Tests

```bash
python3 -m pytest tests/ -v
```

---

## Solución de problemas

### `precios-uy: command not found`

El script se instaló en `~/.local/bin`. Agregalo al PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

O ejecutá con `python3 -m precios_uy` en su lugar.

### Error de permisos al instalar

Usá el entorno virtual o instalá como usuario:

```bash
pip install --user -e .
```

### El scraper no encuentra productos

Posibles causas:
- Cloudflare bloqueando (Tienda Inglesa, Ta-Ta) — `cloudscraper` debería resolverlo
- Las URLs de los supermercados cambiaron — verificar en `precios_uy/scrapers/`
- Timeout muy bajo — aumentar `REQUEST_TIMEOUT` en `.env`

### Base de datos corrupta

Eliminar el archivo y volver a scrapear:

```bash
rm precios_uy.db
precios-uy scrapear
```

### Puerto 8000 en uso

Cambiar el puerto en `.env`:

```env
API_PORT=8080
```
