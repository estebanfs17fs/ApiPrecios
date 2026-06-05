# Precios UY — Documentación

> Consulta de precios de supermercados de Uruguay.

---

## 1. Descripción

Precios UY es un scraper y API REST que recolecta precios de productos de supermercados uruguayos y los expone vía CLI y API REST.

### Supermercados soportados

| Supermercado | Estado | Productos aprox. | Método |
|---|---|---|---|
| **Ta-Ta** | ✅ Funcional | ~236 | API VTEX (cloudscraper) |
| **Disco** | ✅ Funcional | ~100 | HTML scraping |
| **Devoto** | ✅ Funcional | ~100 | HTML scraping |
| **Tienda Inglesa** | ✅ Funcional | ~38 | HTML + cloudscraper (Cloudflare) |
| **Macromercado** | ❌ Sin tienda online | 0 | Catálogo B2B sin precios |

---

## 2. Arquitectura

```
precios_uy/
├── api/              → FastAPI + rutas REST
├── scrapers/         → Scrapers individuales por supermercado
│   ├── base.py       → Clase abstracta ScraperBase
│   ├── tata.py       → API VTEX
│   ├── disco.py      → HTML (Blazor)
│   ├── devoto.py     → HTML (Blazor)
│   ├── tienda_inglesa.py → HTML (GeneXus)
│   └── macromercado.py   → Sin tienda
├── models.py         → Modelo SQLAlchemy (Producto)
├── database.py       → Operaciones de base de datos
├── config.py         → Configuración (pydantic-settings)
├── cli.py            → Interfaz de línea de comandos
└── scheduler.py      → Scraping automático programado
```

---

## 3. Instalación

Ver [`INSTALL.md`](./INSTALL.md) para instrucciones detalladas.

Resumen:

```bash
git clone <repo>
cd precios_uy
python3 -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env
```

---

## 4. Uso CLI

### `precios-uy scrapear`

Ejecuta scraping de todos los supermercados una vez.

```bash
precios-uy scrapear
# Info: Ta-Ta: 236 productos guardados
# Info: Disco: 100 productos guardados
# Info: Devoto: 100 productos guardados
# Info: Tienda Inglesa: 38 productos guardados
```

### `precios-uy listar`

Lista los últimos precios registrados.

```bash
precios-uy listar
precios-uy listar --supermercado Disco
precios-uy listar --categoria "Almacén"
precios-uy listar --limite 50
precios-uy listar -s "Tienda Inglesa" -l 5
```

### `precios-uy buscar <término>`

Busca productos por nombre.

```bash
precios-uy buscar arroz
precios-uy buscar "dulce de leche"
precios-uy buscar leche --limite 5
```

### `precios-uy supermercados`

Lista supermercados con datos.

```bash
precios-uy supermercados
```

### `precios-uy schedule`

Inicia scraping automático cada N horas.

```bash
precios-uy schedule
```

### `python -m precios_uy`

Alternativa si `precios-uy` no está en PATH:

```bash
python3 -m precios_uy scrapear
python3 -m precios_uy listar
```

---

## 5. API REST

Documentación interactiva:
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### `GET /api/productos`

Lista últimos precios. Parámetros: `supermercado`, `categoria`, `limite` (1-500, default 50).

```bash
curl "http://localhost:8000/api/productos?supermercado=Disco&limite=3"
```

### `GET /api/productos/buscar`

Busca por nombre. Parámetros: `q` (requerido), `limite` (1-200, default 20).

```bash
curl "http://localhost:8000/api/productos/buscar?q=arroz"
```

### `GET /api/supermercados`

```bash
curl http://localhost:8000/api/supermercados
```

### `GET /api/categorias`

```bash
curl "http://localhost:8000/api/categorias?supermercado=Disco"
```

### `POST /api/scrapear`

```bash
curl -X POST http://localhost:8000/api/scrapear
```

---

## 6. Base de Datos

### Diagrama

```
┌─────────────────────────────────────┐
│           productos                  │
├─────────────────────────────────────┤
│ id              INTEGER (PK, AI)    │
│ supermercado    VARCHAR(50)  (idx)  │
│ nombre          VARCHAR(300)        │
│ precio          FLOAT               │
│ precio_anterior FLOAT (nullable)    │
│ categoria       VARCHAR(100)        │
│ marca           VARCHAR(100)        │
│ url_producto    VARCHAR(500)        │
│ url_imagen      VARCHAR(500)        │
│ fecha_scraping  DATETIME     (idx)  │
└─────────────────────────────────────┘
```

### Tecnología

- **Motor:** SQLite (por defecto `precios_uy.db`)
- **ORM:** SQLAlchemy 2.0
- Configurable vía `DATABASE_URL` en `.env`
- Se puede cambiar a PostgreSQL/MySQL cambiando la URL

### Operaciones

| Función | Descripción |
|---|---|
| `guardar_productos(lista)` | Inserta productos, retorna cantidad |
| `obtener_ultimos_precios(filtros)` | Último precio por producto |
| `buscar_productos(término)` | Búsqueda ILIKE por nombre |
| `obtener_supermercados()` | Lista de supermercados |
| `obtener_categorias(supermercado)` | Lista de categorías |

---

## 7. Scrapers

### ScraperBase

```python
class ScraperBase(ABC):
    supermercado: str
    def scrapear() -> List[Producto]
    def _get_soup(url) -> BeautifulSoup
    def _parse_precio(texto) -> float
```

Usa `cloudscraper` para bypass de Cloudflare.

### Parsing de precios

Formato uruguayo: `.` = miles, `,` = decimal.

| Entrada | Salida |
|---|---|
| `$ 100` | 100.0 |
| `$ 99,99` | 99.99 |
| `$ 1.234` | 1234.0 |
| `$ 1.234,56` | 1234.56 |
| `UYU 500` | 500.0 |

### Por supermercado

| Supermercado | URL base | Método |
|---|---|---|
| **Ta-Ta** | `tatauy.vtexassets.com` | API VTEX |
| **Disco** | `www.disco.com.uy` | HTML (`div.product-item`) |
| **Devoto** | `www.devoto.com.uy` | HTML (igual que Disco) |
| **Tienda Inglesa** | `www.tiendainglesa.com.uy` | HTML (`div.card-product-container`) |
| **Macromercado** | — | Sin tienda online |

---

## 8. Tests

```bash
# Todos
python3 -m pytest tests/ -v

# Con cobertura
python3 -m pytest tests/ --cov=precios_uy -v

# Tests específicos
python3 -m pytest tests/test_api.py -v
```

### Estructura (67 tests)

| Archivo | Tests | Qué prueba |
|---|---|---|
| `test_models.py` | 7 | Producto, to_dict, persistencia |
| `test_database.py` | 16 | CRUD, filtros, búsqueda |
| `test_api.py` | 15 | Endpoints REST |
| `test_cli.py` | 8 | Comandos CLI |
| `test_scrapers.py` | 13 | parse_precio, registro scrapers |

### Fixtures

| Fixture | Descripción |
|---|---|
| `_test_database` | BD temporal aislada por test |
| `session` | Sesión SQLAlchemy |
| `client` | TestClient FastAPI |
| `runner` | CliRunner Click |
| `productos_db` | 4 productos de prueba |

---

## 9. Sugerencias de mejora

### Corto plazo

- [ ] Paginación completa en Disco/Devoto (más de 20 productos por categoría)
- [ ] Sesión VTEX para Ta-Ta (catálogo completo con autenticación)
- [ ] Caché de resultados
- [ ] Logging a archivo
- [ ] Lifespan events en FastAPI (reemplazar `on_event` deprecado)

### Mediano plazo

- [ ] Historial de precios (tracking semanal)
- [ ] Alertas de cambios de precio
- [ ] Endpoint de comparación entre supermercados
- [ ] Autenticación y rate limiting en API

### Largo plazo

- [ ] Docker-compose para despliegue
- [ ] CI/CD con GitHub Actions
- [ ] Frontend web (React/Vue)
- [ ] PostgreSQL para múltiples instancias
- [ ] Scrapers con Playwright para sitios con JS pesado
- [ ] Gráficos de evolución de precios
