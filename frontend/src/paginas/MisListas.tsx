import { useEffect, useState } from "react";
import { api, fecha, pesos, type Lista } from "../api";
import { Aviso } from "../componentes/Aviso";
import { ir } from "../ruta";

export default function MisListas() {
  const [listas, setListas] = useState<Lista[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupada, setOcupada] = useState<number | null>(null);

  useEffect(() => {
    api.listas().then(setListas, (e) => setError(e.message));
  }, []);

  async function comparar(lista: Lista) {
    setOcupada(lista.id);
    try {
      const r = await api.ejecutar(lista.id);
      ir(`/lista/${lista.id}/resultado/${r.ejecucion!.id}`);
    } catch (e) {
      setError((e as Error).message);
      setOcupada(null);
    }
  }

  async function borrar(lista: Lista) {
    if (!confirm(`¿Borrar la lista "${lista.nombre}"?`)) return;
    try {
      await api.borrar(lista.id);
      setListas((ls) => ls?.filter((l) => l.id !== lista.id) ?? null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section>
      <div className="titulo-pagina">
        <h1>Mis listas</h1>
        <a className="boton primario" href="#/nueva">
          + Nueva lista
        </a>
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {listas === null && !error && <p className="sutil">Cargando…</p>}

      {listas?.length === 0 && (
        <div className="vacio">
          <h2>Armá tu primera lista</h2>
          <p>
            Buscá cada producto y mirá cuánto sale en cada supermercado. Al terminar te decimos
            dónde comprar cada cosa y te armamos una lista para cada súper.
          </p>
          <p>
            Guardala y la próxima vez que vayas a comprar la volvés a comparar con los precios del
            día.
          </p>
          <a className="boton primario" href="#/nueva">
            Empezar una lista
          </a>
        </div>
      )}

      <ul className="tarjetas">
        {listas?.map((l) => (
          <li key={l.id} className="tarjeta lista-guardada">
            <a href={`#/lista/${l.id}`} className="lista-nombre">
              {l.nombre}
            </a>
            <p className="sutil">
              {l.items.length} {l.items.length === 1 ? "producto" : "productos"}
              {l.supermercados && ` · ${l.supermercados.length} supermercados elegidos`}
            </p>
            {l.ultima_ejecucion ? (
              <p className="ultima">
                Última vez ({fecha(l.ultima_ejecucion.fecha)}):{" "}
                <strong>{pesos(l.ultima_ejecucion.total_optimo)}</strong>
                {" · "}
                <a href={`#/lista/${l.id}/resultado/${l.ultima_ejecucion.id}`}>ver</a>
              </p>
            ) : (
              <p className="sutil">Todavía no la comparaste.</p>
            )}
            <div className="acciones">
              <button
                type="button"
                className="boton primario"
                disabled={ocupada !== null}
                onClick={() => comparar(l)}
              >
                {ocupada === l.id ? "Comparando…" : "Comparar con precios de hoy"}
              </button>
              <a className="boton" href={`#/lista/${l.id}`}>
                Editar
              </a>
              <button type="button" className="boton fantasma" onClick={() => borrar(l)}>
                Borrar
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
