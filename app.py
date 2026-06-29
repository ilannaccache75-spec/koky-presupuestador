"""
Presupuestador Mayorista
App Streamlit para generar presupuestos desde papelerabariloche.com.ar
"""
import asyncio
import json
import os
from pathlib import Path

import streamlit as st

# ── Configuración de página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Presupuestador Mayorista",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Login ────────────────────────────────────────────────────────────────────
def _check_password():
    if st.session_state.get("autenticado"):
        return
    st.title("🔐 Presupuestador Koky")
    pwd = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if pwd == st.secrets.get("password", ""):
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

_check_password()

CONFIG_PATH = Path(__file__).parent / "config.json"
COUNTER_PATH = Path(__file__).parent / "contador.json"


# ── Helpers de persistencia ──────────────────────────────────────────────────
def load_config() -> dict:
    defaults = {"empresa": "Mi Empresa", "email": "", "password": "", "markup_default": 30.0}
    if CONFIG_PATH.exists():
        try:
            defaults.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return defaults


def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def next_numero() -> int:
    if COUNTER_PATH.exists():
        data = json.loads(COUNTER_PATH.read_text())
        n = data.get("ultimo", 0) + 1
    else:
        n = 1
    COUNTER_PATH.write_text(json.dumps({"ultimo": n}))
    return n


# ── CSS personalizado ────────────────────────────────────────────────────────
st.markdown("""
<style>
    :root { --rojo: #CC1515; --amarillo: #F5C800; --carbon: #1A1A1A; }
    .main > div { padding-top: 0.5rem; }

    .stButton>button[kind="primary"] {
        background-color: var(--rojo) !important;
        color: white !important; border: none !important;
        font-weight: 700 !important;
    }
    .stButton>button[kind="primary"]:hover { background-color: #A31010 !important; }
    .stButton>button {
        width: 100%;
        border: 1.5px solid var(--rojo) !important;
        color: var(--rojo) !important; font-weight: 600 !important;
    }
    .stButton>button:hover { background-color: #FFF0F0 !important; }

    .total-box {
        background: var(--rojo); color: white; border-radius: 10px;
        padding: 14px 22px; text-align: center;
        font-size: 1.7rem; font-weight: 800; margin: 10px 0;
        border-bottom: 5px solid var(--amarillo);
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: var(--rojo) !important;
        border-bottom-color: var(--rojo) !important; font-weight: 700;
    }
    div[data-testid="metric-container"] {
        background: #FFF8F8; border: 1.5px solid #FFCDD2;
        border-radius: 8px; padding: 10px;
    }
    hr { border-color: #F5E0E0 !important; }
    input:focus, textarea:focus {
        border-color: var(--rojo) !important;
        box-shadow: 0 0 0 1px var(--rojo) !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Inicializar sesión ───────────────────────────────────────────────────────
if "carrito" not in st.session_state:
    st.session_state.carrito = []

if "cfg" not in st.session_state:
    st.session_state.cfg = load_config()

cfg = st.session_state.cfg


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Configuración
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("⚙️ Configuración")

    cfg["empresa"] = st.text_input("Nombre de tu empresa", value=cfg["empresa"])
    cfg["markup_default"] = st.slider(
        "Ganancia por defecto (%)", min_value=0, max_value=200,
        value=int(cfg["markup_default"]), step=1,
    )

    st.divider()
    st.subheader("🔑 Credenciales del portal")
    cfg["email"]    = st.text_input("Email / Usuario", value=cfg["email"])
    cfg["password"] = st.text_input("Contraseña", value=cfg["password"], type="password")

    st.divider()
    st.subheader("🖼️ Logo de la empresa")
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        st.image(str(logo_path), width=160)
        if st.button("🗑️ Quitar logo"):
            logo_path.unlink()
            st.rerun()
    else:
        logo_file = st.file_uploader("Subir logo (PNG o JPG)", type=["png", "jpg", "jpeg"])
        if logo_file:
            logo_path.write_bytes(logo_file.read())
            st.success("Logo guardado ✓")
            st.rerun()

    if st.button("💾 Guardar configuración"):
        save_config(cfg)
        st.success("Guardado ✓")

    st.divider()
    try:
        from scraper import total_productos, ultima_actualizacion
        tot = total_productos()
        ult = ultima_actualizacion()
    except Exception:
        tot, ult = 0, "Nunca"
    st.metric("Productos en base", f"{tot:,}")
    st.caption(f"Última actualización: {ult}")


# ════════════════════════════════════════════════════════════════════════════
# TABS PRINCIPALES
# ════════════════════════════════════════════════════════════════════════════
tab_buscar, tab_carrito, tab_actualizar = st.tabs([
    "🔍 Buscar productos",
    f"🛒 Presupuesto ({len(st.session_state.carrito)})",
    "🔄 Actualizar precios",
])


# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — Buscador
# ────────────────────────────────────────────────────────────────────────────
with tab_buscar:
    from scraper import CATEGORIAS, buscar_productos

    b1, b2 = st.columns([4, 2])
    query   = b1.text_input("Nombre o SKU", placeholder="Ej: cuaderno, lapiz, pegamento...")
    cat_sel = b2.selectbox("Categoría", ["Todas"] + [c.capitalize() for c in CATEGORIAS])

    try:
        tot_db = total_productos()
    except Exception:
        tot_db = 0

    if tot_db == 0:
        st.info("⚠️ La base de precios está vacía. Andá a la pestaña **Actualizar precios** primero.")
    elif not query:
        st.markdown("*Escribí algo arriba para buscar productos...*")
    else:
        resultados = buscar_productos(query, cat_sel)
        if not resultados:
            st.warning("No se encontraron productos para esa búsqueda.")
        else:
            st.caption(f"{len(resultados)} resultado(s)")
            for prod in resultados:
                rc1, rc2, rc3, rc4 = st.columns([5, 2, 2, 1])
                rc1.markdown(f"**{prod['nombre']}**")
                rc2.markdown(
                    f"SKU: `{prod['sku'] or '—'}`  \n"
                    f"Cat: {(prod['categoria'] or '').capitalize()}"
                )
                precio_str = f"$ {prod['precio']:,.2f}" if prod['precio'] else "Sin precio"
                rc3.markdown(f"**{precio_str}**")
                if rc4.button("➕", key=f"add_{prod['id']}"):
                    existente = next(
                        (x for x in st.session_state.carrito if x["id"] == prod["id"]), None
                    )
                    if existente:
                        existente["cantidad"] += 1
                    else:
                        costo = prod["precio"] or 0
                        mkp   = float(cfg["markup_default"])
                        st.session_state.carrito.append({
                            "id":            prod["id"],
                            "sku":           prod.get("sku") or "",
                            "nombre":        prod["nombre"],
                            "precio_costo":  costo,
                            "cantidad":      1,
                            "markup":        mkp,
                            "precio_custom": costo * (1 + mkp / 100),
                        })
                    st.rerun()
                st.divider()


# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — Carrito / Presupuesto
# ────────────────────────────────────────────────────────────────────────────
with tab_carrito:
    # Fila de controles globales
    mc1, mc2, mc3 = st.columns([2, 2, 4])
    markup_global = mc1.number_input(
        "Ganancia global (%)", min_value=0.0, max_value=500.0,
        value=float(cfg["markup_default"]), step=0.5, format="%.1f",
    )
    if mc2.button("Aplicar % a todos", use_container_width=True):
        for item in st.session_state.carrito:
            item["markup"] = markup_global
            item["precio_custom"] = item["precio_costo"] * (1 + markup_global / 100)
        st.rerun()
    cliente = mc3.text_input("Cliente", placeholder="Nombre del cliente")

    if not st.session_state.carrito:
        st.info("El presupuesto está vacío. Buscá productos en la pestaña **Buscar productos**.")
    else:
        total_presup = 0.0
        items_a_borrar = []

        # Encabezado de columnas
        h1, h2, h3, h4, h5, h6 = st.columns([6, 2, 2, 2, 2, 1])
        h1.caption("Descripción (editable)")
        h2.caption("Cantidad")
        h3.caption("Ganancia %")
        h4.caption("Precio unit.")
        h5.caption("Subtotal")
        h6.caption("")
        st.divider()

        for i, item in enumerate(st.session_state.carrito):
            # Garantizar campos en ítems viejos o corrompidos
            if "markup" not in item:
                item["markup"] = markup_global
            item["markup"] = min(float(item["markup"]), 500.0)
            if "nombre_custom" not in item:
                item["nombre_custom"] = item["nombre"]
            if "precio_custom" not in item:
                item["precio_custom"] = item["precio_costo"] * (1 + item["markup"] / 100)

            ic1, ic2, ic3, ic4, ic5, ic6 = st.columns([6, 2, 2, 2, 2, 1])

            new_nombre = ic1.text_input(
                "desc", value=item["nombre_custom"],
                key=f"nom_{i}", label_visibility="collapsed"
            )
            new_cant = ic2.number_input(
                "cant", min_value=1, max_value=9999,
                value=int(item["cantidad"]), key=f"cant_{i}",
                label_visibility="collapsed"
            )
            new_markup = ic3.number_input(
                "mkp", min_value=0, max_value=500,
                value=int(item["markup"]), step=1,
                key=f"mkp_{i}", label_visibility="collapsed"
            )

            # Si cambió el %, recalculamos precio; si no, usamos el precio guardado
            markup_cambio = new_markup != int(item["markup"])
            precio_base   = item["precio_costo"] * (1 + new_markup / 100) if markup_cambio else item["precio_custom"]

            new_precio = ic4.number_input(
                "prc", min_value=0, max_value=9_999_999,
                value=int(precio_base), step=1,
                key=f"prc_{i}", label_visibility="collapsed"
            )

            subtotal = float(new_precio) * new_cant
            total_presup += subtotal
            ic5.markdown(f"**$ {subtotal:,.0f}**")

            if ic6.button("🗑️", key=f"del_{i}"):
                items_a_borrar.append(i)

            changed = (
                new_cant   != item["cantidad"]      or
                markup_cambio                        or
                new_nombre != item["nombre_custom"] or
                int(new_precio) != int(item["precio_custom"])
            )
            if changed:
                st.session_state.carrito[i]["cantidad"]      = new_cant
                st.session_state.carrito[i]["markup"]        = float(new_markup)
                st.session_state.carrito[i]["nombre_custom"] = new_nombre
                st.session_state.carrito[i]["precio_custom"] = (
                    item["precio_costo"] * (1 + new_markup / 100) if markup_cambio else float(new_precio)
                )
                st.rerun()

        for idx in reversed(items_a_borrar):
            st.session_state.carrito.pop(idx)
        if items_a_borrar:
            st.rerun()

        # ── IVA ──────────────────────────────────────────────────────────────
        iva_modo = st.radio(
            "IVA",
            ["Sin IVA", "+ IVA 21%", "IVA incluido"],
            horizontal=True,
            help="'+ IVA 21%' suma el impuesto al total. 'IVA incluido' muestra solo el total sin desglose.",
        )

        iva_monto   = total_presup * 0.21 if iva_modo == "+ IVA 21%" else 0.0
        total_final = total_presup + iva_monto

        if iva_modo == "+ IVA 21%":
            st.markdown(
                f'<div class="total-box">'
                f'Subtotal &nbsp; $ {total_presup:,.0f} &nbsp;+&nbsp; IVA 21% &nbsp; $ {iva_monto:,.0f}'
                f'<br><span style="font-size:2rem; font-weight:900">TOTAL &nbsp; $ {total_final:,.0f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        elif iva_modo == "IVA incluido":
            st.markdown(
                f'<div class="total-box">TOTAL &nbsp; $ {total_final:,.0f}'
                f'<br><span style="font-size:0.9rem; font-weight:400; opacity:.85">IVA incluido</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="total-box">TOTAL &nbsp; $ {total_final:,.0f}</div>',
                unsafe_allow_html=True,
            )

        notas = st.text_area("Notas (opcional)", height=60, placeholder="Condiciones de pago, entrega, etc.")

        col_pdf, col_xls, col_vac, _ = st.columns([2, 2, 2, 4])

        def _generar(formato: str):
            if not cliente.strip():
                st.error("Ingresá el nombre del cliente.")
                return
            try:
                numero = next_numero()
                items_export = [
                    {**it, "markup": it.get("markup", markup_global)}
                    for it in st.session_state.carrito
                ]
                if formato == "pdf":
                    from generar_pdf import generar_pdf
                    logo = Path(__file__).parent / "logo.png"
                    archivo = generar_pdf(
                        items      = items_export,
                        markup_pct = markup_global,
                        empresa    = cfg["empresa"],
                        cliente    = cliente.strip(),
                        numero     = numero,
                        notas      = notas,
                        logo_path  = logo if logo.exists() else None,
                        iva_modo   = iva_modo,
                    )
                else:
                    from generar_excel import generar
                    archivo = generar(
                        items      = items_export,
                        markup_pct = markup_global,
                        empresa    = cfg["empresa"],
                        cliente    = cliente.strip(),
                        numero     = numero,
                        notas      = notas,
                        iva_modo   = iva_modo,
                    )
                st.success(f"✅ Presupuesto N°{numero:05d} generado.")
                st.info(f"📁 Guardado en:\n`{archivo}`")
                if st.button("📂 Abrir carpeta", key="open_folder"):
                    os.startfile(str(archivo.parent))
            except Exception as e:
                st.error(f"Error al generar: {e}")

        with col_pdf:
            if st.button("📄 Generar PDF", type="primary", use_container_width=True):
                _generar("pdf")
        with col_xls:
            if st.button("📊 Generar Excel", use_container_width=True):
                _generar("excel")
        with col_vac:
            if st.button("🗑️ Vaciar todo", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()


# ────────────────────────────────────────────────────────────────────────────
# TAB 3 — Actualizar precios
# ────────────────────────────────────────────────────────────────────────────
with tab_actualizar:
    st.subheader("🔄 Actualizar base de precios")

    st.markdown("### Opción 1 — Importar JSON desde Chrome (recomendado)")
    st.markdown(
        "Este método obtiene el **mejor precio** de cada producto "
        "(el precio con el mayor descuento por cantidad). "
        "Tarda entre 10 y 20 minutos según la cantidad de productos.\n\n"
        "**Pasos:**\n"
        "1. Abrí Chrome y entrá a [papelerabariloche.com.ar](https://www.papelerabariloche.com.ar) con tu cuenta\n"
        "2. Apretá **F12** → pestaña **Console**\n"
        "3. Pegá el script que está abajo y presioná Enter\n"
        "4. Esperá a que termine y se descargue el archivo `productos_mejor_precio.json`\n"
        "5. Subí ese archivo acá abajo"
    )

    with st.expander("📋 Script para pegar en la consola de Chrome"):
        st.code(r"""
(async () => {
  const BASE = 'https://www.papelerabariloche.com.ar';
  const CATS = ['escolar','marroquineria','comercial','regaleria','artistica','resmas','tecnologia','agendas'];
  const CONC = 8;

  const parseAR = t => {
    const m = t && t.match(/\d[\d.]*,\d{2}/);
    if (!m) return null;
    const v = parseFloat(m[0].replace(/\./g,'').replace(',','.'));
    return v > 0 ? v : null;
  };

  const bestPrice = html => {
    // busca patrones "c/u $ 4.561,81" de la tabla de descuentos
    const ms = [...html.matchAll(/c\/u\s*\$\s*([\d.]+,\d{2})/gi)];
    if (ms.length) {
      const ps = ms.map(m => parseAR(m[1])).filter(Boolean);
      if (ps.length) return Math.min(...ps);
    }
    // fallback: precio con descuento del listado
    const doc = new DOMParser().parseFromString(html, 'text/html');
    for (const sel of ['.pb-price','.pb-precio-descuento','[class*="price"]']) {
      const p = parseAR(doc.querySelector(sel)?.textContent);
      if (p) return p;
    }
    return null;
  };

  const products = [];
  for (const cat of CATS) {
    console.log(`📁 ${cat}`);
    let page = 1, links = [];
    while (true) {
      const url = page===1 ? `${BASE}/${cat}` : `${BASE}/${cat}/${page}`;
      const doc = new DOMParser().parseFromString(await (await fetch(url,{credentials:'include'})).text(),'text/html');
      const cards = doc.querySelectorAll('.pb-product');
      if (!cards.length) break;
      cards.forEach(c => {
        const a = c.querySelector('a[href*="/produto/"],a[href*="/producto/"]') || c.querySelector('a');
        const n = c.querySelector('.pb-product-title');
        const s = c.querySelector('.pb-product-sku span:last-child');
        if (!a||!n) return;
        const href = a.href;
        links.push({id:href.split('/').pop(), nombre:n.textContent.trim(), sku:s?.textContent.trim()||null, url:href, categoria:cat});
      });
      if (!doc.querySelector('a[rel="next"],.pagination .next:not(.disabled)')) break;
      page++;
    }
    console.log(`  → ${links.length} productos`);
    for (let i=0; i<links.length; i+=CONC) {
      const batch = links.slice(i,i+CONC);
      const htmls = await Promise.all(batch.map(p=>fetch(p.url,{credentials:'include'}).then(r=>r.text()).catch(()=>'')));
      batch.forEach((p,j)=>products.push({...p, precio:bestPrice(htmls[j])}));
      if (i%80===0) console.log(`  → ${Math.min(i+CONC,links.length)}/${links.length}`);
    }
  }
  console.log(`✅ ${products.length} productos. Descargando...`);
  const a = Object.assign(document.createElement('a'),{
    href: URL.createObjectURL(new Blob([JSON.stringify(products)],{type:'application/json'})),
    download:'productos_mejor_precio.json'
  });
  document.body.appendChild(a); a.click(); a.remove();
})();
""", language="javascript")

    json_file = st.file_uploader("📂 Subir archivo JSON descargado", type=["json"])
    if json_file:
        if st.button("⬆️ Importar a la base de datos", type="primary"):
            try:
                from scraper import importar_json
                datos = json.loads(json_file.read().decode("utf-8"))
                n = importar_json(datos)
                st.success(f"✅ {n:,} productos importados con los mejores precios.")
                st.balloons()
            except Exception as e:
                st.error(f"Error al importar: {e}")

    st.divider()
    st.markdown("### Opción 2 — Actualización automática (precio estándar)")
    st.caption("Esta opción usa el precio base del listado, sin considerar descuentos por cantidad.")

    if not cfg.get("email") or not cfg.get("password"):
        st.error("⚠️ Primero configurá el email y contraseña en el panel izquierdo.")
    else:
        if st.button("▶️ Iniciar actualización automática"):
            log_area = st.empty()
            progress = st.progress(0)
            logs: list[str] = []

            def callback(msg: str):
                logs.append(msg)
                log_area.code("\n".join(logs[-30:]), language=None)

            try:
                from scraper import scrape, CATEGORIAS
                callback("Iniciando scraper...")
                total = asyncio.run(scrape(cfg["email"], cfg["password"], callback))
                progress.progress(1.0)
                st.success(f"✅ Actualización completada: {total:,} productos.")
                st.balloons()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Error inesperado: {e}")
                st.caption("Verificá las credenciales y la conexión a internet.")
