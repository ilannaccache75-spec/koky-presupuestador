"""
Abre Chrome (ya logueado) y scrapea el mejor precio de descuento por cantidad
para cada producto marcado como "DESCUENTO POR CANTIDAD" en el Excel.

Uso:
  python scraper_mejores_precios.py

Guarda resultados en mejores_precios.json e importa al DB.
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "productos.db"
EXCEL_PATH = Path(r"C:\Users\ilan\Downloads\Papelera Bariloche - Lista de Precios 26-06-2026 (1).xlsx")
SKU_JSON = Path(__file__).parent / "skus_con_descuento.json"
RESULTADO_JSON = Path(__file__).parent / "mejores_precios.json"

# ── JS que corre en Chrome para scrapear un batch ──────────────────────────
JS_BATCH = r"""
async (skus) => {
  const BATCH_SIZE = 20;
  const results = [];

  async function fetchMejorPrecio(sku) {
    const q = sku.replace(/-/g, '');
    try {
      const form = new FormData();
      form.append('frmSearchSubmitted', '1');
      form.append('txtSearch', q);
      const resp = await fetch('https://www.papelerabariloche.com.ar/', {
        method: 'POST', body: form, credentials: 'include'
      });
      const html = await resp.text();
      const doc = new DOMParser().parseFromString(html, 'text/html');

      let targetUrl = resp.url;
      // Si la búsqueda NO redirigió al producto, buscar el card con SKU exacto
      if (!targetUrl.includes('/producto/')) {
        const cards = doc.querySelectorAll('.pb-product');
        for (const card of cards) {
          const siteSku = card.querySelector('.pb-product-sku span:last-child')?.textContent?.trim();
          if (siteSku === q) {
            targetUrl = card.querySelector('a[href*="/producto/"]')?.href || '';
            break;
          }
        }
        if (!targetUrl.includes('/producto/')) {
          // Fallback: primer producto del listado
          const fb = doc.querySelector('a[href*="sharer.php"]');
          if (fb) {
            const m = fb.href.match(/u=(https[^&]+)/);
            targetUrl = m ? decodeURIComponent(m[1]) : '';
          }
        }
        if (!targetUrl.includes('/producto/')) {
          return {sku, error: 'not_found'};
        }
        // Segunda request al producto
        const resp2 = await fetch(targetUrl, {credentials: 'include'});
        const html2 = await resp2.text();
        const doc2 = new DOMParser().parseFromString(html2, 'text/html');
        return extraerPrecio(sku, targetUrl, doc2);
      }

      return extraerPrecio(sku, targetUrl, doc);
    } catch(e) {
      return {sku, error: e.message};
    }
  }

  function extraerPrecio(sku, url, doc) {
    const bidRaw = doc.querySelector('.pb-product-bid-price')?.textContent?.trim() || '';
    const bidPrecio = parseFloat(bidRaw.replace(/[^\d,]/g,'').replace(',','.')) || 0;

    const tbody = doc.querySelector('.table-condensed tbody');
    const rows = tbody ? [...tbody.querySelectorAll('tr')] : [];
    const discRows = rows.filter(tr => tr.querySelectorAll('td').length >= 3);
    const lastRow = discRows[discRows.length - 1];
    const mejorRaw = lastRow?.querySelectorAll('td')[2]?.textContent?.trim() || '';
    const mejorPrecio = mejorRaw
      ? parseFloat(mejorRaw.replace(/[^\d,]/g,'').replace(',','.'))
      : bidPrecio;

    return {sku, url, bidPrecio, mejorPrecio: mejorPrecio || bidPrecio};
  }

  // Procesar en batches
  for (let i = 0; i < skus.length; i += BATCH_SIZE) {
    const batch = skus.slice(i, i + BATCH_SIZE);
    const batchResults = await Promise.allSettled(batch.map(s => fetchMejorPrecio(s)));
    for (const r of batchResults) {
      results.push(r.status === 'fulfilled' ? r.value : {sku: '?', error: r.reason?.message});
    }
    // Pequeña pausa entre batches para no saturar el servidor
    await new Promise(res => setTimeout(res, 300));
  }

  return results;
}
"""

def importar_mejores_precios(resultados: list) -> dict:
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat(timespec="seconds")
    actualizados = 0
    no_encontrados = 0

    for r in resultados:
        if r.get("error") or not r.get("mejorPrecio"):
            no_encontrados += 1
            continue
        sku_excel = r["sku"]
        sku_site = sku_excel.replace("-", "")
        precio = r["mejorPrecio"]
        url = r.get("url", "")

        # Actualizar por SKU (con o sin guion)
        rows = conn.execute(
            "SELECT id FROM productos WHERE sku = ? OR sku = ?", (sku_excel, sku_site)
        ).fetchall()
        if rows:
            for (prod_id,) in rows:
                conn.execute(
                    "UPDATE productos SET precio=?, url=?, actualizado=? WHERE id=?",
                    (precio, url, now, prod_id)
                )
            actualizados += len(rows)
        else:
            no_encontrados += 1

    conn.execute(
        "INSERT OR REPLACE INTO ultima_actualizacion (id, fecha) VALUES (1, ?)", (now,)
    )
    conn.commit()
    conn.close()
    return {"actualizados": actualizados, "no_encontrados": no_encontrados}


def main():
    from playwright.sync_api import sync_playwright
    import sys

    skus_data = json.loads(SKU_JSON.read_text(encoding="utf-8"))
    skus = [x["sku"] for x in skus_data]
    total = len(skus)
    print(f"Procesando {total} productos con descuento...")

    resultados = []
    CHUNK = 500  # procesar de a 500 en el browser

    with sync_playwright() as pw:
        # Abrir Chrome real (con el perfil donde está logueado)
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        for start in range(0, total, CHUNK):
            chunk = skus[start:start + CHUNK]
            end = min(start + CHUNK, total)
            print(f"  Batch {start+1}-{end} de {total}...")
            chunk_results = page.evaluate(JS_BATCH, chunk)
            resultados.extend(chunk_results)
            ok = sum(1 for r in chunk_results if not r.get("error"))
            print(f"    OK: {ok}/{len(chunk)}")

        browser.close()

    RESULTADO_JSON.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nResultados guardados en {RESULTADO_JSON}")

    stats = importar_mejores_precios(resultados)
    print(f"Importados al DB: actualizados={stats['actualizados']}, no encontrados={stats['no_encontrados']}")


if __name__ == "__main__":
    main()
