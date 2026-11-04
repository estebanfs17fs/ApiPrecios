# Precios UY — Documentación

> Precios de supermercados de Uruguay: scraping, API REST y una web para armar la lista de compras y ver dónde conviene comprarla.

---

## 1. Descripción

Precios UY recolecta precios de supermercados uruguayos, los guarda en una base de datos con su historial, reconoce el mismo producto en distintos supermercados y permite comparar una lista de compras completa.

### Supermercados

| Supermercado | Método | Notas |
|---|---|---|
| **Ta-Ta** | API VTEX | Trae EAN (código de barras) |
| **El Dorado** | API VTEX | Trae EAN |
| **Disco** | Navegador (Playwright) | Scroll infinito y lazy loading |
| **Devoto** | Navegador (Playwright) | Igual que Disco |
| **Tienda Inglesa** | HTML paginado + cloudscraper | Hoy bloquea con Cloudflare (403) |
| **Frog** | HTML paginado (nopCommerce) | Categorías raíz del menú, `?pagenumber=N`; pausa entre páginas porque corta con 405 |
| **Kinko** | — | Sin tienda online (la web es solo institucional) |
| **Macromercado** | — | Sin tienda online |

---

## 2. Arquitectura

```
precios_uy/
├── api/              → FastAPI: rutas REST y servidor (también sirve la web)
├── web/              → Frontend (HTML + JS, sin build): buscar, lista, comparar
├── scrapers/
│   ├── base.py         → ScraperBase (cloudscraper, parseo de precios)
│   ├── vtex_base.py    → Base para tiendas VTEX (Ta-Ta, El Dorado)
│   ├── browser_base.py → Base con Playwright: scroll infinito + lazy loading
│   └── ...             → un archivo por supermercado
├── normalizacion.py  → Nombres y medidas normalizados para comparar productos
├── models.py         → Producto, HistorialPrecio, ProductoScrapeado
├── database.py       → Guardado, búsqueda, agrupación y comparación de listas
├── scheduler.py      → Scraping (manual o periódico)
├── config.py         → Configuración (pydantic-settings / .env)
└── cli.py            → Línea de comandos
```

---

## 3. Instalación

Ver [`INSTALL.md`](./INSTALL.md). Resumen:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -e .
python -m playwright install chromium   # necesario para Disco y Devoto
cp .env.example .env
```

---

## 4. Uso

### Web

```bash
python run_api.py
```

Abrir `http://localhost:8000/`. Desde ahí se buscan productos (agrupados por supermercado), se agregan a la lista con cantidades, se eligen los supermercados a considerar y se compara. La lista queda guardada en el navegador.

Si la base está vacía, la web ofrece un botón para traer precios.

### CLI

```bash
precios-uy scrapear                    # todos los supermercados
precios-uy scrapear --force -s disco   # solo Disco, aunque los datos estén frescos
precios-uy listar -s Disco -l 20
precios-uy buscar "dulce de leche"
precios-uy comparar "arroz 1 kg"       # el mismo producto en cada supermercado
precios-uy supermercados
precios-uy renormalizar                # recalcula medidas tras cambiar las reglas de normalización
precios-uy schedule                    # scraping automático cada SCRAP_INTERVAL_HOURS
```

---

## 5. API REST

Documentación interactiva en `http://localhost:8000/docs`.

| Método y ruta | Qué hace |
|---|---|
| `GET /api/productos` | Productos con su precio actual (`supermercado`, `categoria`, `limite`) |
| `GET /api/productos/buscar?q=` | Búsqueda sin tildes, en cualquier orden; entiende medidas (`azucar 1 kg`) |
| `GET /api/productos/comparar?q=` | Busca y agrupa el mismo producto entre supermercados |
| `GET /api/productos/{id}` | Detalle e historial de precios |
| `POST /api/lista/comparar` | Compara una lista de compras (ver abajo) |
| `GET /api/supermercados` | Supermercados con datos |
| `GET /api/categorias` | Categorías |
| `POST /api/scrapear` | Lanza el scraping en segundo plano (`force`, `supermercado`) |
| `GET /api/scrapear` | Estado del scraping en curso |

### Comparar una lista

```bash
curl -X POST http://localhost:8000/api/lista/comparar \
  -H 'Content-Type: application/json' \
  -d '{"items": [{"producto_id": 12, "cantidad": 2}, {"texto": "leche 1 l"}],
       "supermercados": ["Disco", "Ta-Ta"]}'
```

Cada item es un `producto_id` (se busca ese producto o su equivalente en cada supermercado) o un `texto`. Con texto se elige un mismo producto para todos: entre los que coinciden y están en casi todos los supermercados, el más barato en promedio. Donde ese producto no está se toma el más barato que coincida y el detalle lo marca con `"aproximado": true`. La respuesta trae:

- `supermercados`: total, encontrados, faltantes y detalle por supermercado, ordenados de mejor a peor.
- `recomendado`: el supermercado más barato que tiene toda la lista.
- `combinacion_optima`: comprando cada producto donde está más barato (los aproximados solo cuentan si no hay otra opción).

---

## 6. Base de datos

```
productos                               precios (historial)
─────────────────────────────           ───────────────────────
id                PK                    id           PK
supermercado      (idx)                 producto_id  FK → productos.id
identificador     sku, url o nombre     precio
nombre                                  precio_anterior
nombre_normalizado (idx)                fecha        (idx)
medida            "1000g", "1500ml", "6x1000ml"
ean               (idx)
precio            precio actual
precio_anterior   precio de lista si hay descuento
categoria, marca, url_producto, url_imagen
creado, actualizado
UNIQUE(supermercado, identificador)
```

- Cada scrapeo actualiza el producto existente; solo se agrega una fila a `precios` si el precio cambió.
- Si se abre una base del esquema anterior (una fila por scrapeo), se migra sola al arrancar.
- SQLite por defecto; cualquier motor de SQLAlchemy vía `DATABASE_URL`.

### Cómo se reconoce el mismo producto

1. Si los dos tienen EAN, se comparan por EAN.
2. Si no, se normaliza el nombre (sin tildes, mayúsculas, palabras vacías ni orden) y la medida (`1 Kg` = `1000 grs`; los packs llevan la cantidad: `6 x 1 L` y `Pack x 6 1 L` = `6x1000ml`). Con medidas distintas son productos distintos; si no, se exige al menos 60 % de palabras en común, u 80 % si solo uno de los dos tiene medida.
3. Un producto entra a un grupo solo si es equivalente a todos los del grupo, así un nombre sin medida no une presentaciones distintas.

---

## 7. Scraping con scroll infinito (Disco, Devoto)

`BrowserScraperBase` abre cada categoría con Chromium y:

1. Baja de a una pantalla leyendo los productos en cada paso, así todos entran en pantalla y cargan precio e imagen. Lo leído se acumula aunque el sitio lo saque del DOM después.
2. Al llegar abajo espera a que aparezcan productos nuevos (hasta `SCROLL_ESPERA_MS`), y hace clic en "Ver más" si hay botón.
3. Termina cuando pasan `SCROLL_PACIENCIA` vueltas sin productos nuevos.
4. Escucha las respuestas JSON del sitio: si traen productos estilo VTEX, también se usan (y aportan EAN).
5. Si la página dice "N productos" y se obtuvieron menos, lo avisa en el log.
6. Descubre las categorías desde el menú del sitio, además de la lista fija.

Los selectores CSS están como atributos de clase (`SELECTOR_ITEM`, `SELECTOR_PRECIO`, ...) para ajustarlos si el sitio cambia.

### Configuración

| Variable | Default | Uso |
|---|---|---|
| `CHROMIUM_PATH` | vacío | Ruta a un Chromium propio |
| `BROWSER_HEADLESS` | `true` | `false` para ver el navegador mientras scrapea |
| `SCROLL_MAX_PASOS` | 1000 | Tope de vueltas por categoría |
| `SCROLL_PACIENCIA` | 5 | Vueltas sin novedades antes de cortar |
| `SCROLL_ESPERA_MS` | 4000 | Espera máxima por vuelta |

---

## 8. Tests

```bash
python -m pytest tests/ -v
python -m pytest tests/ -m "not navegador"   # sin las pruebas que abren Chromium
```

`tests/test_browser_scraper.py` levanta un sitio local que imita a Disco/Devoto (scroll infinito, precios que aparecen al entrar en pantalla, lista virtualizada y botón "Ver más") y verifica que se obtengan todos los productos.

---

## 9. Pendientes

- [ ] Probar los scrapers contra los sitios reales y ajustar selectores si cambiaron.
- [ ] Gráfico de evolución de precios en la web (el historial ya está en la API).
- [ ] Alertas de cambios de precio.
- [ ] Autenticación y rate limiting en la API.
