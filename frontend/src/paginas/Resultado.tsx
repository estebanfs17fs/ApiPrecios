import { useEffect, useState } from "react";
import { api, fecha, pesos, type Fila, type Lista, type Resultado } from "../api";
import { Aviso } from "../componentes/Aviso";
import { Historial } from "../componentes/Historial";
import { ir } from "../ruta";

function claveTildes(ejecucion: number) {
  return `listita_tildes_${ejecucion}`;
}

function leerTildes(ejecucion: number): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(claveTildes(ejecucion)) ?? "[]"));
  } catch {
    return new Set();
  }
}

function textoParaCompartir(lista: Lista, r: Resultado) {
  const lineas = [`${lista.nombre}: ${pesos(r.combinacion_optima.total)}`];
  for (const s of r.combinacion_optima.por_supermercado) {
    lineas.push("", `${s.supermercado} (${pesos(s.total)})`);
    for (const f of s.detalle) {
      lineas.push(`- ${f.cantidad} × ${f.producto.nombre}: ${pesos(f.subtotal)}`);
    }
  }
  if (r.combinacion_optima.faltantes.length) {
    lineas.push("", "No encontrado:");
    for (const i of r.combinacion_optima.faltantes) lineas.push(`- ${r.items[i].descripcion}`);
  }
  return lineas.join("\n");
}

export default function ResultadoLista({ id, ejecucionId }: { id: number; ejecucionId: number }) {
  const [lista, setLista] = useState<Lista | null>(null);
  const [r, setR] = useState<Resultado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recomparando, setRecomparando] = useState(false);
  const [tildes, setTildes] = useState(() => leerTildes(ejecucionId));
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    Promise.all([api.lista(id), api.ejecucion(id, ejecucionId)]).then(
      ([l, res]) => {
        setLista(l);
        setR(res);
      },
      (e) => setError(e.message),
    );
  }, [id, ejecucionId]);

  function tildar(clave: string) {
    setTildes((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(clave)) nuevo.delete(clave);
      else nuevo.add(clave);
      try {
        localStorage.setItem(claveTildes(ejecucionId), JSON.stringify([...nuevo]));
      } catch {
        /* sin almacenamiento */
      }
      return nuevo;
    });
  }

  async function recomparar() {
    setRecomparando(true);
    try {
      const nuevo = await api.ejecutar(id);
      ir(`/lista/${id}/resultado/${nuevo.ejecucion!.id}`);
    } catch (e) {
      setError((e as Error).message);
      setRecomparando(false);
    }
  }

  async function copiar() {
    if (!lista || !r) return;
    try {
      await navigator.clipboard.writeText(textoParaCompartir(lista, r));
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setError("No se pudo copiar al portapapeles");
    }
  }

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!lista || !r) return <p className="sutil">Cargando…</p>;

  const optima = r.combinacion_optima;
  const recomendado = r.supermercados.find((s) => s.supermercado === r.recomendado);
  const ahorro = recomendado ? recomendado.total - optima.total : 0;
  const ultima = lista.ejecuciones?.[0];
  const esVieja = ultima && ultima.id !== ejecucionId;

  return (
    <section className="resultado-pagina">
      <div className="titulo-pagina">
        <a href="#/" className="volver">
          ← Mis listas
        </a>
        <a href={`#/lista/${id}`} className="boton fantasma chico">
          Editar lista
        </a>
      </div>

      <h1>{lista.nombre}</h1>
      <p className="sutil">
        Precios del {fecha(r.ejecucion!.fecha)}
        {esVieja && (
          <>
            {" · "}
            <a href={`#/lista/${id}/resultado/${ultima.id}`}>ver la más reciente</a>
          </>
        )}
      </p>

      <div className="resumen">
        <div className="resumen-principal">
          <span className="sutil">Comprando cada cosa donde está más barata</span>
          <strong className="total">{pesos(optima.total)}</strong>
          <span className="sutil">
            en {optima.por_supermercado.length}{" "}
            {optima.por_supermercado.length === 1 ? "supermercado" : "supermercados"}
          </span>
        </div>
        {recomendado && optima.por_supermercado.length > 1 && (
          <div className="resumen-alternativa">
            <span className="sutil">Si preferís ir a un solo lugar</span>
            <strong>
              {recomendado.supermercado}: {pesos(recomendado.total)}
            </strong>
            {ahorro > 0.5 && (
              <span className="ahorro">Dividiendo la compra ahorrás {pesos(ahorro)}</span>
            )}
          </div>
        )}
      </div>

      <div className="acciones">
        <button type="button" className="boton primario" disabled={recomparando} onClick={recomparar}>
          {recomparando ? "Comparando…" : "Volver a comparar con precios de hoy"}
        </button>
        <button type="button" className="boton" onClick={copiar}>
          {copiado ? "¡Copiada!" : "Copiar las listas"}
        </button>
      </div>

      <h2 className="subtitulo">Dónde comprar cada cosa</h2>
      <div className="por-super">
        {optima.por_supermercado.map((s) => (
          <article key={s.supermercado} className="tarjeta lista-super">
            <header>
              <h3>{s.supermercado}</h3>
              <span className="total-super">{pesos(s.total)}</span>
            </header>
            <ul>
              {s.detalle.map((f) => (
                <FilaCompra
                  key={f.indice}
                  fila={f}
                  pedido={r.items[f.indice].descripcion}
                  tildado={tildes.has(`${s.supermercado}-${f.indice}`)}
                  onTildar={() => tildar(`${s.supermercado}-${f.indice}`)}
                />
              ))}
            </ul>
          </article>
        ))}
      </div>

      {optima.faltantes.length > 0 && (
        <Aviso tipo="info">
          No encontramos en ningún supermercado:{" "}
          {optima.faltantes.map((i) => r.items[i].descripcion).join(", ")}.
        </Aviso>
      )}

      <h2 className="subtitulo">Toda la lista en un solo supermercado</h2>
      <table className="tabla">
        <thead>
          <tr>
            <th>Supermercado</th>
            <th className="num">Tiene</th>
            <th className="num">Total</th>
          </tr>
        </thead>
        <tbody>
          {r.supermercados.map((s) => (
            <tr key={s.supermercado} className={s.supermercado === r.recomendado ? "destacada" : ""}>
              <td>
                {s.supermercado}
                {s.faltantes.length > 0 && (
                  <span className="sutil chico bloque">
                    Le falta: {s.faltantes.map((i) => r.items[i].descripcion).join(", ")}
                  </span>
                )}
              </td>
              <td className="num">
                {s.encontrados}/{r.items.length}
              </td>
              <td className="num">{pesos(s.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {lista.ejecuciones && lista.ejecuciones.length > 0 && (
        <>
          <h2 className="subtitulo">Cómo cambió el total</h2>
          <Historial id={id} ejecuciones={lista.ejecuciones} actual={ejecucionId} />
        </>
      )}
    </section>
  );
}

function FilaCompra({
  fila,
  pedido,
  tildado,
  onTildar,
}: {
  fila: Fila;
  pedido: string;
  tildado: boolean;
  onTildar: () => void;
}) {
  const p = fila.producto;
  return (
    <li className={tildado ? "tildado" : ""}>
      <label>
        <input type="checkbox" checked={tildado} onChange={onTildar} />
        <span className="fila-texto">
          <span className="fila-nombre">
            {fila.cantidad} × {p.nombre}
          </span>
          {fila.aproximado && (
            <span className="etiqueta">parecido a "{pedido}"</span>
          )}
          <span className="sutil chico bloque">
            {pesos(p.precio)} c/u
            {p.url_producto && (
              <>
                {" · "}
                <a href={p.url_producto} target="_blank" rel="noopener noreferrer">
                  ver en la web
                </a>
              </>
            )}
          </span>
        </span>
        <span className="subtotal">{pesos(fila.subtotal)}</span>
      </label>
    </li>
  );
}
