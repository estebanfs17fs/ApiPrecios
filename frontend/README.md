# Listita — app web

Interfaz para armar la lista del súper usando la API de Precios UY (la carpeta de arriba).

- Buscás cada producto y ves cuánto sale en cada supermercado, del más barato al más caro.
- Al terminar te dice dónde comprar cada cosa: arma una lista para cada supermercado, con casillas para ir tildando, y la compara con comprar todo en un solo lugar.
- La lista queda guardada. Cuando volvés a comprar la comparás de nuevo con los precios de ese día; cada comparación queda en el historial para ver cómo cambió el total.

No hay cuentas: el navegador genera un id anónimo (`X-Usuario`) y la API le muestra solo sus listas. Si se borran los datos del navegador, se pierde el acceso a esas listas.

## Desarrollo

Necesita Node 20 o más nuevo y la API corriendo (`python run_api.py` en la carpeta de arriba, puerto 8000).

```bash
npm install
npm run dev          # http://localhost:5173, /api se reenvía a localhost:8000
```

Si la API corre en otro lado: `API_URL=http://otra-maquina:8000 npm run dev`.

## Producción

```bash
npm run build        # genera dist/
```

`dist/` son archivos estáticos. Hay que servirlos junto con la API en el mismo dominio (reenviando `/api`), o compilar con `VITE_API_URL=https://mi-api.com npm run build` para que llame a la API directamente (la API ya permite CORS).

Con Docker, desde la carpeta de arriba: `docker compose up --build` levanta la API en el puerto 8000 y la app en el 8080.
