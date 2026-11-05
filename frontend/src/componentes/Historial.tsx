import { fechaHora, pesos, type ResumenEjecucion } from "../api";

// Total de la lista en cada comparación: un gráfico chico y la lista de fechas.
export function Historial({
  id,
  ejecuciones,
  actual,
}: {
  id: number;
  ejecuciones: ResumenEjecucion[]; // de la más nueva a la más vieja
  actual: number;
}) {
  const cronologicas = [...ejecuciones].reverse();
  const totales = cronologicas.map((e) => e.total_optimo);
  const min = Math.min(...totales);
  const max = Math.max(...totales);
  const ancho = 600;
  const alto = 120;
  const margen = 10;
  const x = (i: number) =>
    cronologicas.length === 1
      ? ancho / 2
      : margen + (i * (ancho - 2 * margen)) / (cronologicas.length - 1);
  const y = (v: number) =>
    max === min ? alto / 2 : alto - margen - ((v - min) * (alto - 2 * margen)) / (max - min);
  const puntos = cronologicas.map((e, i) => `${x(i)},${y(e.total_optimo)}`).join(" ");

  return (
    <div className="historial">
      {cronologicas.length > 1 && (
        <svg
          viewBox={`0 0 ${ancho} ${alto}`}
          className="grafico"
          role="img"
          aria-label={`El total fue de ${pesos(totales[0])} a ${pesos(totales[totales.length - 1])}`}
        >
          <polyline points={puntos} fill="none" className="linea" />
          {cronologicas.map((e, i) => (
            <circle
              key={e.id}
              cx={x(i)}
              cy={y(e.total_optimo)}
              r={e.id === actual ? 6 : 4}
              className={e.id === actual ? "punto actual" : "punto"}
            >
              <title>
                {fechaHora(e.fecha)}: {pesos(e.total_optimo)}
              </title>
            </circle>
          ))}
        </svg>
      )}
      <ul className="ejecuciones">
        {ejecuciones.map((e, i) => {
          const anterior = ejecuciones[i + 1];
          const cambio = anterior ? e.total_optimo - anterior.total_optimo : 0;
          return (
            <li key={e.id} className={e.id === actual ? "actual" : ""}>
              <a href={`#/lista/${id}/resultado/${e.id}`}>{fechaHora(e.fecha)}</a>
              <span className="num">{pesos(e.total_optimo)}</span>
              {anterior && Math.abs(cambio) >= 0.5 ? (
                <span className={`variacion ${cambio > 0 ? "sube" : "baja"}`}>
                  {cambio > 0 ? "▲" : "▼"} {pesos(Math.abs(cambio))}
                </span>
              ) : (
                <span className="variacion sutil">—</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
