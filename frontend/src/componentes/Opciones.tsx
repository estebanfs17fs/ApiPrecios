import { useState } from "react";
import { pesos, type Producto } from "../api";

const VISIBLES = 4;

// Precios de un producto en cada supermercado, del más barato al más caro.
const simple = (t: string) => t.toLowerCase().replace(/[^a-z0-9]/g, "");

export function Opciones({
  ofertas,
  cantidad = 1,
  compacto = false,
  nombre = "",
}: {
  ofertas: Producto[];
  cantidad?: number;
  compacto?: boolean;
  /** nombre del item: el de cada supermercado se muestra solo si es distinto */
  nombre?: string;
}) {
  const [todas, setTodas] = useState(false);
  if (!ofertas.length) {
    return <p className="sutil chico">No está en los supermercados elegidos.</p>;
  }
  const ordenadas = [...ofertas].sort((a, b) => a.precio - b.precio);
  const mejor = ordenadas[0].precio;
  const mostradas = todas ? ordenadas : ordenadas.slice(0, VISIBLES);

  return (
    <ol className={`opciones ${compacto ? "compacto" : ""}`}>
      {mostradas.map((o, i) => (
        <li key={o.id} className={i === 0 && ordenadas.length > 1 ? "mejor" : ""}>
          <span className="super">{o.supermercado}</span>
          <span className="precio">
            {o.precio_anterior && o.precio_anterior > o.precio && (
              <s className="sutil">{pesos(o.precio_anterior)}</s>
            )}{" "}
            {pesos(o.precio)}
          </span>
          {!compacto && (
            <span className="dif sutil">
              {i === 0
                ? ordenadas.length > 1
                  ? "el más barato"
                  : "único"
                : `+${pesos((o.precio - mejor) * cantidad)}`}
            </span>
          )}
          {!compacto && simple(o.nombre) !== simple(nombre) && (
            <span className="nombre-en-super sutil" title={o.nombre}>
              {o.url_producto ? (
                <a href={o.url_producto} target="_blank" rel="noopener noreferrer">
                  {o.nombre}
                </a>
              ) : (
                o.nombre
              )}
            </span>
          )}
        </li>
      ))}
      {ordenadas.length > VISIBLES && (
        <li className="mas">
          <button type="button" className="enlace" onClick={() => setTodas(!todas)}>
            {todas ? "Ver menos" : `Ver ${ordenadas.length - VISIBLES} más`}
          </button>
        </li>
      )}
    </ol>
  );
}
