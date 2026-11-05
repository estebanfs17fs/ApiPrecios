// Cliente de la API de Precios UY.

export interface Producto {
  id: number;
  supermercado: string;
  nombre: string;
  precio: number;
  precio_anterior: number | null;
  categoria: string | null;
  marca: string | null;
  ean: string | null;
  medida: string | null;
  url_producto: string | null;
  url_imagen: string | null;
  fecha_scraping: string | null;
}

export interface Grupo {
  nombre: string;
  medida: string | null;
  ean: string | null;
  url_imagen: string | null;
  precio_min: number;
  precio_max: number;
  supermercado_mas_barato: string;
  ofertas: Producto[];
}

export interface Item {
  producto_id?: number | null;
  texto?: string | null;
  nombre: string;
  cantidad: number;
}

export interface ResumenEjecucion {
  id: number;
  fecha: string;
  total_optimo: number;
  recomendado: string | null;
  total_recomendado: number | null;
}

export interface Lista {
  id: number;
  nombre: string;
  items: Item[];
  supermercados: string[] | null;
  creado: string;
  actualizado: string;
  ultima_ejecucion: ResumenEjecucion | null;
  ejecuciones?: ResumenEjecucion[];
}

export interface Fila {
  indice: number;
  cantidad: number;
  producto: Producto;
  subtotal: number;
  aproximado: boolean;
}

export interface Resultado {
  items: { indice: number; descripcion: string; cantidad: number }[];
  supermercados: {
    supermercado: string;
    total: number;
    encontrados: number;
    faltantes: number[];
    detalle: Fila[];
  }[];
  recomendado: string | null;
  combinacion_optima: {
    total: number;
    detalle: Fila[];
    faltantes: number[];
    por_supermercado: { supermercado: string; total: number; detalle: Fila[] }[];
  };
  ejecucion?: ResumenEjecucion;
}

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const CLAVE_USUARIO = "listita_usuario";

// Sin cuentas: cada navegador tiene un id anónimo y la API le muestra solo sus listas.
function usuario(): string {
  let id: string | null = null;
  try {
    id = localStorage.getItem(CLAVE_USUARIO);
  } catch {
    /* sin almacenamiento */
  }
  if (!id) {
    id = crypto.randomUUID().replace(/-/g, "");
    try {
      localStorage.setItem(CLAVE_USUARIO, id);
    } catch {
      /* la sesión dura lo que la pestaña */
    }
  }
  return id;
}

export class ErrorApi extends Error {
  constructor(
    public estado: number,
    mensaje: string,
  ) {
    super(mensaje);
  }
}

async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const headers = new Headers(opciones.headers);
  headers.set("X-Usuario", usuario());
  if (opciones.body) headers.set("Content-Type", "application/json");
  let r: Response;
  try {
    r = await fetch(BASE + ruta, { ...opciones, headers });
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con la API");
  }
  if (!r.ok) {
    let detalle = `Error ${r.status}`;
    try {
      const cuerpo = await r.json();
      if (typeof cuerpo.detail === "string") detalle = cuerpo.detail;
    } catch {
      /* sin cuerpo */
    }
    throw new ErrorApi(r.status, detalle);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

const json = (datos: unknown) => JSON.stringify(datos);

export const api = {
  supermercados: () =>
    pedir<{ supermercados: string[] }>("/api/supermercados").then((r) => r.supermercados),

  buscar: (q: string, signal?: AbortSignal) =>
    pedir<{ grupos: Grupo[] }>(`/api/productos/comparar?q=${encodeURIComponent(q)}`, {
      signal,
    }).then((r) => r.grupos),

  opciones: (productoId: number) =>
    pedir<{ opciones: Producto[] }>(`/api/productos/${productoId}/opciones`).then(
      (r) => r.opciones,
    ),

  listas: () => pedir<{ listas: Lista[] }>("/api/listas").then((r) => r.listas),
  lista: (id: number) => pedir<Lista>(`/api/listas/${id}`),
  crear: (datos: Pick<Lista, "nombre" | "items" | "supermercados">) =>
    pedir<Lista>("/api/listas", { method: "POST", body: json(datos) }),
  actualizar: (id: number, datos: Pick<Lista, "nombre" | "items" | "supermercados">) =>
    pedir<Lista>(`/api/listas/${id}`, { method: "PUT", body: json(datos) }),
  borrar: (id: number) => pedir<void>(`/api/listas/${id}`, { method: "DELETE" }),
  ejecutar: (id: number) => pedir<Resultado>(`/api/listas/${id}/ejecutar`, { method: "POST" }),
  ejecucion: (id: number, ejecucionId: number) =>
    pedir<Resultado>(`/api/listas/${id}/ejecuciones/${ejecucionId}`),
};

const formato = new Intl.NumberFormat("es-UY", {
  style: "currency",
  currency: "UYU",
  maximumFractionDigits: 2,
});
export const pesos = (n: number) => formato.format(n);

export const fecha = (iso: string) =>
  new Date(iso).toLocaleDateString("es-UY", { day: "numeric", month: "short", year: "numeric" });

export const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-UY", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
