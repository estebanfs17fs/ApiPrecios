import { useEffect, useRef, useState } from "react";
import { api, pesos, type Grupo, type Item, type Producto } from "../api";
import { Aviso } from "../componentes/Aviso";
import { Opciones } from "../componentes/Opciones";
import { ir } from "../ruta";

// En el editor cada item lleva además sus precios en cada supermercado.
interface ItemEditor extends Item {
  clave: string;
  opciones?: Producto[];
}

const BORRADOR = "listita_borrador";
let contador = 0;
const nuevaClave = () => `i${Date.now()}_${contador++}`;

function leerBorrador(): { nombre: string; items: ItemEditor[] } | null {
  try {
    return JSON.parse(localStorage.getItem(BORRADOR) ?? "null");
  } catch {
    return null;
  }
}

function guardarBorrador(nombre: string, items: ItemEditor[]) {
  try {
    if (items.length || nombre) localStorage.setItem(BORRADOR, JSON.stringify({ nombre, items }));
    else localStorage.removeItem(BORRADOR);
  } catch {
    /* sin almacenamiento */
  }
}

function sinItemsDeEditor(items: ItemEditor[]): Item[] {
  return items.map(({ producto_id, texto, nombre, cantidad }) => ({
    producto_id: producto_id ?? null,
    texto: texto ?? null,
    nombre,
    cantidad,
  }));
}

export default function Editor({ id }: { id: number | null }) {
  const [nombre, setNombre] = useState("");
  const [items, setItems] = useState<ItemEditor[]>([]);
  const [supers, setSupers] = useState<string[]>([]);
  const [elegidos, setElegidos] = useState<Set<string>>(new Set());
  const [cargando, setCargando] = useState(id !== null);
  const [guardando, setGuardando] = useState<null | "guardar" | "comparar">(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  // carga inicial: supermercados y la lista (o el borrador si es nueva)
  useEffect(() => {
    let vigente = true;
    (async () => {
      try {
        const todos = await api.supermercados();
        if (!vigente) return;
        setSupers(todos);
        if (id === null) {
          const b = leerBorrador();
          if (b) {
            setNombre(b.nombre);
            setItems(b.items);
          }
          setElegidos(new Set(todos));
          return;
        }
        const lista = await api.lista(id);
        if (!vigente) return;
        setNombre(lista.nombre);
        setItems(lista.items.map((it) => ({ ...it, clave: nuevaClave() })));
        setElegidos(new Set(lista.supermercados ?? todos));
      } catch (e) {
        if (vigente) setError((e as Error).message);
      } finally {
        if (vigente) setCargando(false);
      }
    })();
    return () => {
      vigente = false;
    };
  }, [id]);

  // los items guardados no traen precios: se piden al abrir la lista
  useEffect(() => {
    const faltan = items.filter((it) => it.producto_id && !it.opciones);
    for (const it of faltan) {
      api.opciones(it.producto_id!).then(
        (opciones) =>
          setItems((xs) => xs.map((x) => (x.clave === it.clave ? { ...x, opciones } : x))),
        () =>
          setItems((xs) => xs.map((x) => (x.clave === it.clave ? { ...x, opciones: [] } : x))),
      );
    }
  }, [items]);

  useEffect(() => {
    if (id === null && !cargando) guardarBorrador(nombre, items);
  }, [id, nombre, items, cargando]);

  const filtrar = (ops: Producto[] | undefined) =>
    ops?.filter((o) => elegidos.has(o.supermercado)) ?? [];

  const estimado = items.reduce((suma, it) => {
    const mejor = filtrar(it.opciones)[0];
    return mejor ? suma + mejor.precio * it.cantidad : suma;
  }, 0);

  function agregarGrupo(g: Grupo) {
    const productoId = g.ofertas[0].id;
    setItems((xs) => {
      const ya = xs.find((x) => x.producto_id && g.ofertas.some((o) => o.id === x.producto_id));
      if (ya) {
        return xs.map((x) => (x === ya ? { ...x, cantidad: x.cantidad + 1 } : x));
      }
      return [
        ...xs,
        { clave: nuevaClave(), producto_id: productoId, nombre: g.nombre, cantidad: 1 },
      ];
    });
    setAviso(`Agregaste ${g.nombre}`);
  }

  function agregarTexto(texto: string) {
    setItems((xs) => [...xs, { clave: nuevaClave(), texto, nombre: texto, cantidad: 1 }]);
    setAviso(`Agregaste "${texto}"`);
  }

  const cambiar = (clave: string, cambios: Partial<ItemEditor>) =>
    setItems((xs) => xs.map((x) => (x.clave === clave ? { ...x, ...cambios } : x)));

  function alternarSuper(s: string) {
    setElegidos((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(s)) {
        if (nuevo.size > 1) nuevo.delete(s);
      } else nuevo.add(s);
      return nuevo;
    });
  }

  async function guardar(yComparar: boolean) {
    setError(null);
    if (!items.length) return;
    setGuardando(yComparar ? "comparar" : "guardar");
    const datos = {
      nombre: nombre.trim() || "Mi lista",
      items: sinItemsDeEditor(items),
      supermercados: elegidos.size === supers.length ? null : [...elegidos],
    };
    try {
      const lista = id === null ? await api.crear(datos) : await api.actualizar(id, datos);
      if (id === null) guardarBorrador("", []);
      if (yComparar) {
        const r = await api.ejecutar(lista.id);
        ir(`/lista/${lista.id}/resultado/${r.ejecucion!.id}`);
      } else if (id === null) {
        ir(`/lista/${lista.id}`);
      } else {
        setAviso("Lista guardada");
        setGuardando(null);
      }
    } catch (e) {
      setError((e as Error).message);
      setGuardando(null);
    }
  }

  if (cargando) return <p className="sutil">Cargando…</p>;

  return (
    <section className="editor">
      <div className="titulo-pagina">
        <a href="#/" className="volver">
          ← Mis listas
        </a>
      </div>

      <label className="campo-nombre">
        <span className="visualmente-oculto">Nombre de la lista</span>
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre de la lista (ej.: Compra de la semana)"
          maxLength={120}
        />
      </label>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {supers.length === 0 && !error && (
        <Aviso tipo="info">
          La API todavía no tiene precios. Corré el scraping y volvé a esta página.
        </Aviso>
      )}

      {supers.length > 1 && (
        <fieldset className="supers">
          <legend>Supermercados a comparar</legend>
          {supers.map((s) => (
            <button
              type="button"
              key={s}
              className={`chip ${elegidos.has(s) ? "activo" : ""}`}
              aria-pressed={elegidos.has(s)}
              onClick={() => alternarSuper(s)}
            >
              {s}
            </button>
          ))}
        </fieldset>
      )}

      <Buscador elegidos={elegidos} onGrupo={agregarGrupo} onTexto={agregarTexto} />

      <p className="visualmente-oculto" aria-live="polite">
        {aviso}
      </p>

      <h2 className="subtitulo">
        Tu lista {items.length > 0 && <span className="contador">{items.length}</span>}
      </h2>
      {items.length === 0 ? (
        <p className="sutil vacio-lista">
          Todavía está vacía. Buscá un producto arriba y agregalo: vas a ver cuánto sale en cada
          supermercado.
        </p>
      ) : (
        <ul className="items">
          {items.map((it) => (
            <li key={it.clave} className="item">
              <div className="item-cabeza">
                <span className="item-nombre">{it.nombre}</span>
                <Cantidad valor={it.cantidad} onCambio={(c) => cambiar(it.clave, { cantidad: c })} />
                <button
                  type="button"
                  className="quitar"
                  aria-label={`Quitar ${it.nombre}`}
                  onClick={() => setItems((xs) => xs.filter((x) => x.clave !== it.clave))}
                >
                  ✕
                </button>
              </div>
              {it.texto ? (
                <p className="sutil chico">
                  Texto libre: al comparar se busca lo más parecido en cada supermercado.
                </p>
              ) : it.opciones === undefined ? (
                <p className="sutil chico">Buscando precios…</p>
              ) : (
                <Opciones ofertas={filtrar(it.opciones)} cantidad={it.cantidad} nombre={it.nombre} />
              )}
            </li>
          ))}
        </ul>
      )}

      {items.length > 0 && (
        <div className="pie-editor">
          <div>
            <span className="sutil chico">Estimado comprando lo más barato</span>
            <strong className="estimado">{pesos(estimado)}</strong>
          </div>
          <div className="acciones">
            <button
              type="button"
              className="boton"
              disabled={guardando !== null}
              onClick={() => guardar(false)}
            >
              {guardando === "guardar" ? "Guardando…" : "Guardar"}
            </button>
            <button
              type="button"
              className="boton primario"
              disabled={guardando !== null}
              onClick={() => guardar(true)}
            >
              {guardando === "comparar" ? (
                "Comparando…"
              ) : (
                <>
                  <span className="solo-ancho">Listo: </span>¿Dónde compro?
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function Cantidad({ valor, onCambio }: { valor: number; onCambio: (n: number) => void }) {
  return (
    <span className="cantidad">
      <button type="button" aria-label="Uno menos" onClick={() => onCambio(Math.max(1, valor - 1))}>
        −
      </button>
      <input
        type="number"
        min={1}
        value={valor}
        aria-label="Cantidad"
        onChange={(e) => onCambio(Math.max(1, Number(e.target.value) || 1))}
      />
      <button type="button" aria-label="Uno más" onClick={() => onCambio(valor + 1)}>
        +
      </button>
    </span>
  );
}

function Buscador({
  elegidos,
  onGrupo,
  onTexto,
}: {
  elegidos: Set<string>;
  onGrupo: (g: Grupo) => void;
  onTexto: (t: string) => void;
}) {
  const [q, setQ] = useState("");
  const [grupos, setGrupos] = useState<Grupo[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const termino = q.trim();
    if (termino.length < 2) {
      setGrupos(null);
      return;
    }
    const control = new AbortController();
    const espera = setTimeout(async () => {
      setBuscando(true);
      setError(null);
      try {
        setGrupos(await api.buscar(termino, control.signal));
      } catch (e) {
        if (!control.signal.aborted) setError((e as Error).message);
      } finally {
        if (!control.signal.aborted) setBuscando(false);
      }
    }, 300);
    return () => {
      clearTimeout(espera);
      control.abort();
    };
  }, [q]);

  const visibles = (grupos ?? [])
    .map((g) => ({ ...g, ofertas: g.ofertas.filter((o) => elegidos.has(o.supermercado)) }))
    .filter((g) => g.ofertas.length > 0)
    .slice(0, 12);

  function elegir(g: Grupo) {
    onGrupo(g);
    setQ("");
    input.current?.focus();
  }

  return (
    <div className="buscador">
      <label className="caja-busqueda">
        <span className="visualmente-oculto">Buscar producto</span>
        <input
          ref={input}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscá un producto: leche, arroz 1 kg, yerba…"
          autoComplete="off"
        />
      </label>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {q.trim().length >= 2 && (
        <div className="resultados">
          {buscando && !grupos && <p className="sutil chico">Buscando…</p>}
          {grupos && visibles.length === 0 && !buscando && (
            <p className="sutil chico">No encontré "{q.trim()}" en los supermercados elegidos.</p>
          )}
          <ul>
            {visibles.map((g, i) => (
              <li key={`${g.nombre}-${i}`} className="resultado">
                {g.url_imagen ? (
                  <img src={g.url_imagen} alt="" loading="lazy" />
                ) : (
                  <span className="sin-imagen" aria-hidden="true" />
                )}
                <div className="resultado-cuerpo">
                  <span className="resultado-nombre">{g.nombre}</span>
                  <Opciones ofertas={g.ofertas} compacto />
                </div>
                <button type="button" className="boton primario chico" onClick={() => elegir(g)}>
                  Agregar
                </button>
              </li>
            ))}
          </ul>
          <button type="button" className="boton fantasma chico" onClick={() => {
            onTexto(q.trim());
            setQ("");
          }}>
            ¿No es ninguno? Agregar "{q.trim()}" como texto
          </button>
        </div>
      )}
    </div>
  );
}
