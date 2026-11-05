import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Editor from "./paginas/Editor";
import MisListas from "./paginas/MisListas";
import ResultadoLista from "./paginas/Resultado";
import "./estilos.css";

// Rutas con hash (#/lista/3) para poder servir la app como archivos estáticos.
type Ruta =
  | { pagina: "inicio" }
  | { pagina: "editor"; id: number | null }
  | { pagina: "resultado"; id: number; ejecucion: number };

function leerRuta(): Ruta {
  const partes = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (partes[0] === "nueva") return { pagina: "editor", id: null };
  if (partes[0] === "lista" && partes[1]) {
    const id = Number(partes[1]);
    if (partes[2] === "resultado" && partes[3]) {
      return { pagina: "resultado", id, ejecucion: Number(partes[3]) };
    }
    return { pagina: "editor", id };
  }
  return { pagina: "inicio" };
}

function App() {
  const [ruta, setRuta] = useState(leerRuta);
  useEffect(() => {
    const cambio = () => {
      setRuta(leerRuta());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);

  return (
    <>
      <header className="cabecera">
        <a href="#/" className="marca">
          <span className="logo" aria-hidden="true" />
          Listita
        </a>
        <span className="lema">Tu lista, al mejor precio</span>
      </header>
      <main className="contenido">
        {ruta.pagina === "inicio" && <MisListas />}
        {ruta.pagina === "editor" && <Editor key={ruta.id ?? "nueva"} id={ruta.id} />}
        {ruta.pagina === "resultado" && (
          <ResultadoLista key={ruta.ejecucion} id={ruta.id} ejecucionId={ruta.ejecucion} />
        )}
      </main>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
