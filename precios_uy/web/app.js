// Frontend de Lista de precios: buscar productos, armar la lista y compararla.
const CLAVE_LISTA = "precios_uy_lista";
const CLAVE_SUPERS = "precios_uy_supers_excluidos";

const $ = (sel) => document.querySelector(sel);
const pesos = new Intl.NumberFormat("es-UY", { style: "currency", currency: "UYU" });

function leer(clave, porDefecto) {
  try {
    return JSON.parse(localStorage.getItem(clave)) ?? porDefecto;
  } catch {
    return porDefecto;
  }
}
function guardar(clave, valor) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    /* sin almacenamiento: la lista vive solo en esta pestaña */
  }
}
function esc(texto) {
  const d = document.createElement("div");
  d.textContent = texto ?? "";
  return d.innerHTML;
}

let lista = leer(CLAVE_LISTA, []);
let excluidos = new Set(leer(CLAVE_SUPERS, []));
let supermercados = [];

async function api(ruta, opciones) {
  const r = await fetch(ruta, opciones);
  if (!r.ok) throw new Error(`Error ${r.status}`);
  return r.json();
}

// ------------------------------------------------------------------ búsqueda

async function buscar(q) {
  const cont = $("#resultados");
  cont.innerHTML = '<p class="sutil">Buscando…</p>';
  try {
    const datos = await api(`/api/productos/comparar?q=${encodeURIComponent(q)}`);
    cont.innerHTML = "";
    if (!datos.grupos.length) {
      cont.innerHTML = `<p class="sutil">No encontré "${esc(q)}".</p>`;
    }
    for (const g of datos.grupos.slice(0, 40)) cont.appendChild(tarjetaGrupo(g));
    const libre = document.createElement("p");
    libre.className = "sutil";
    libre.innerHTML = `¿No es ninguno? <button type="button" class="secundario">Agregar "${esc(q)}" como texto</button>`;
    libre.querySelector("button").onclick = () =>
      agregar({ texto: q, nombre: q, cantidad: 1 });
    cont.appendChild(libre);
  } catch (e) {
    cont.innerHTML = `<p class="falta">No se pudo buscar (${esc(e.message)}).</p>`;
  }
}

function tarjetaGrupo(g) {
  const nodo = $("#tpl-grupo").content.firstElementChild.cloneNode(true);
  const img = nodo.querySelector("img");
  if (g.url_imagen) img.src = g.url_imagen;
  else img.style.visibility = "hidden";
  nodo.querySelector(".grupo-nombre").textContent = g.nombre;
  const ul = nodo.querySelector(".ofertas");
  g.ofertas.forEach((o, i) => {
    const li = document.createElement("li");
    if (i === 0 && g.ofertas.length > 1) li.className = "mejor";
    const antes = o.precio_anterior
      ? `<span class="tachado">${pesos.format(o.precio_anterior)}</span>`
      : "";
    const nombre = o.url_producto
      ? `<a href="${esc(o.url_producto)}" target="_blank" rel="noopener">${esc(o.supermercado)}</a>`
      : esc(o.supermercado);
    li.innerHTML = `<span>${nombre}</span><span>${antes}${pesos.format(o.precio)}</span>`;
    ul.appendChild(li);
  });
  nodo.querySelector(".agregar").onclick = () =>
    agregar({ producto_id: g.ofertas[0].id, nombre: g.nombre, cantidad: 1 });
  return nodo;
}

// ------------------------------------------------------------------ lista

function agregar(item) {
  const existente = lista.find((x) =>
    item.producto_id ? x.producto_id === item.producto_id : x.texto === item.texto
  );
  if (existente) existente.cantidad += 1;
  else lista.push(item);
  guardarLista();
}

function guardarLista() {
  guardar(CLAVE_LISTA, lista);
  pintarLista();
}

function pintarLista() {
  const ul = $("#lista");
  ul.innerHTML = "";
  lista.forEach((item, i) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="nombre">${esc(item.nombre)}${item.texto ? ' <span class="sutil">(texto)</span>' : ""}</span>
      <input type="number" min="1" step="1" value="${item.cantidad}" aria-label="Cantidad">
      <button type="button" class="quitar" aria-label="Quitar">✕</button>`;
    li.querySelector("input").onchange = (e) => {
      item.cantidad = Math.max(1, Number(e.target.value) || 1);
      guardarLista();
    };
    li.querySelector(".quitar").onclick = () => {
      lista.splice(i, 1);
      guardarLista();
    };
    ul.appendChild(li);
  });
  $("#lista-vacia").hidden = lista.length > 0;
  $("#btn-comparar").disabled = lista.length === 0;
  $("#btn-vaciar").disabled = lista.length === 0;
}

function pintarSupers() {
  const cont = $("#supers-opciones");
  cont.innerHTML = "";
  for (const s of supermercados) {
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" ${excluidos.has(s) ? "" : "checked"}> ${esc(s)}`;
    label.querySelector("input").onchange = (e) => {
      if (e.target.checked) excluidos.delete(s);
      else excluidos.add(s);
      guardar(CLAVE_SUPERS, [...excluidos]);
    };
    cont.appendChild(label);
  }
  $("#filtro-supers").hidden = supermercados.length === 0;
}

// ------------------------------------------------------------------ comparación

async function comparar() {
  const cont = $("#comparacion");
  cont.innerHTML = '<p class="sutil">Comparando…</p>';
  const elegidos = supermercados.filter((s) => !excluidos.has(s));
  try {
    const r = await api("/api/lista/comparar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: lista.map(({ producto_id, texto, cantidad }) => ({ producto_id, texto, cantidad })),
        supermercados: elegidos.length ? elegidos : null,
      }),
    });
    pintarComparacion(r);
  } catch (e) {
    cont.innerHTML = `<p class="falta">No se pudo comparar (${esc(e.message)}).</p>`;
  }
}

function pintarComparacion(r) {
  const nombreItem = (i) => esc(r.items[i].descripcion);
  const cont = $("#comparacion");
  let html = "";

  if (r.recomendado) {
    const mejor = r.supermercados.find((s) => s.supermercado === r.recomendado);
    html += `<div class="recomendado">Te conviene <strong>${esc(r.recomendado)}</strong>:
      toda la lista por <strong>${pesos.format(mejor.total)}</strong>.</div>`;
  } else {
    html += `<div class="aviso">Ningún supermercado tiene toda la lista. Mirá los faltantes abajo.</div>`;
  }

  html += `<table><thead><tr><th>Supermercado</th><th class="num">Total</th><th class="num">Tiene</th></tr></thead><tbody>`;
  for (const s of r.supermercados) {
    html += `<tr><td>${esc(s.supermercado)}</td><td class="num">${pesos.format(s.total)}</td>
      <td class="num">${s.encontrados}/${r.items.length}</td></tr>`;
  }
  html += `</tbody></table>`;

  for (const s of r.supermercados) {
    html += `<details><summary>${esc(s.supermercado)}: detalle</summary><table><tbody>`;
    for (const d of s.detalle) {
      const otro = d.aproximado
        ? `<br><span class="sutil">No tiene el mismo producto que los demás; es el más barato parecido.</span>`
        : "";
      html += `<tr><td>${d.cantidad} × ${esc(d.producto.nombre)}${otro}</td><td class="num">${pesos.format(d.subtotal)}</td></tr>`;
    }
    for (const i of s.faltantes) {
      html += `<tr><td class="falta">Falta: ${nombreItem(i)}</td><td></td></tr>`;
    }
    html += `</tbody></table></details>`;
  }

  const opt = r.combinacion_optima;
  if (opt.detalle.length) {
    const ahorro = r.recomendado
      ? r.supermercados.find((s) => s.supermercado === r.recomendado).total - opt.total
      : 0;
    html += `<h3>Comprando cada cosa donde está más barata: ${pesos.format(opt.total)}</h3>`;
    if (ahorro > 0.5) {
      html += `<p class="sutil">Ahorrás ${pesos.format(ahorro)} frente a ir solo a ${esc(r.recomendado)}, pero tenés que ir a más de un lugar.</p>`;
    }
    html += `<table><tbody>`;
    for (const d of opt.detalle) {
      html += `<tr><td>${d.cantidad} × ${esc(d.producto.nombre)}<br><span class="sutil">${esc(d.producto.supermercado)}</span></td>
        <td class="num">${pesos.format(d.subtotal)}</td></tr>`;
    }
    for (const i of opt.faltantes) {
      html += `<tr><td class="falta">No está en ningún lado: ${nombreItem(i)}</td><td></td></tr>`;
    }
    html += `</tbody></table>`;
  }
  cont.innerHTML = html;
}

// ------------------------------------------------------------------ datos

async function cargarSupermercados() {
  try {
    supermercados = (await api("/api/supermercados")).supermercados;
  } catch {
    supermercados = [];
  }
  pintarSupers();
  $("#sin-datos").hidden = supermercados.length > 0;
  $("#estado-datos").textContent = supermercados.length
    ? `${supermercados.length} supermercados con precios`
    : "";
}

async function scrapear() {
  const btn = $("#btn-scrapear");
  btn.disabled = true;
  try {
    await api("/api/scrapear?force=true", { method: "POST" });
  } catch (e) {
    btn.disabled = false;
    $("#estado-datos").textContent = `No se pudo iniciar (${e.message})`;
    return;
  }
  const revisar = async () => {
    const estado = await api("/api/scrapear").catch(() => null);
    if (estado && estado.en_curso) {
      const listos = Object.keys(estado.resultados).length;
      $("#estado-datos").textContent = `Trayendo precios… (${listos} supermercados listos)`;
      setTimeout(revisar, 5000);
    } else {
      btn.disabled = false;
      await cargarSupermercados();
    }
  };
  revisar();
}

$("#form-buscar").onsubmit = (e) => {
  e.preventDefault();
  const q = $("#q").value.trim();
  if (q) buscar(q);
};
$("#btn-comparar").onclick = comparar;
$("#btn-vaciar").onclick = () => {
  lista = [];
  $("#comparacion").innerHTML = "";
  guardarLista();
};
$("#btn-scrapear").onclick = scrapear;

pintarLista();
cargarSupermercados();
