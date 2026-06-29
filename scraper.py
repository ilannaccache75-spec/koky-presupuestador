"""
Scraper para papelerabariloche.com.ar
Se loguea con Playwright y descarga productos con precios.
"""
import asyncio
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "productos.db"
BASE_URL = "https://www.papelerabariloche.com.ar"

CATEGORIAS = [
    "escolar", "marroquineria", "comercial",
    "regaleria", "artistica", "resmas", "tecnologia", "agendas"
]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id          TEXT PRIMARY KEY,
            sku         TEXT,
            nombre      TEXT NOT NULL,
            precio      REAL,
            categoria   TEXT,
            url         TEXT,
            actualizado TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ultima_actualizacion (
            id   INTEGER PRIMARY KEY CHECK (id = 1),
            fecha TEXT
        )
    """)
    conn.commit()
    return conn


def parse_precio(texto: str) -> float | None:
    if not texto:
        return None
    limpio = re.sub(r"[^\d,.]", "", texto).replace(".", "").replace(",", ".")
    try:
        return float(limpio) if limpio else None
    except ValueError:
        return None


async def scrape(email: str, password: str, callback=None):
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    def log(msg: str):
        if callback:
            callback(msg)
        else:
            print(msg)

    conn = init_db()
    total = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await ctx.new_page()

        # ── LOGIN ──────────────────────────────────────────────
        log("Conectando al portal...")
        await page.goto(BASE_URL, wait_until="domcontentloaded")

        # Buscar link de login
        for selector in ['a[href*="login"]', 'a[href*="cuenta"]',
                         'a:text("Iniciar")', 'a:text("Ingresar")',
                         'a:text("Login")', 'a:text("Sesión")']:
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    await el.click()
                    await page.wait_for_load_state("domcontentloaded")
                    break
            except Exception:
                pass

        # Completar formulario
        try:
            await page.fill('input[type="email"]', email, timeout=5000)
        except PWTimeout:
            await page.fill('input[name*="mail"], input[name*="user"]', email)

        await page.fill('input[type="password"]', password)
        await page.click('button[type="submit"], input[type="submit"]')
        await page.wait_for_load_state("domcontentloaded")

        # Verificar login
        current = page.url
        if "login" in current or "ingresar" in current:
            await browser.close()
            conn.close()
            raise ValueError("Login fallido: verificá el usuario y contraseña.")

        log("✅ Login exitoso. Descargando productos...")

        # ── SCRAPING POR CATEGORÍA ──────────────────────────────
        now = datetime.now().isoformat(timespec="seconds")

        for cat in CATEGORIAS:
            log(f"  Categoría: {cat}")
            page_num = 1

            while True:
                url = f"{BASE_URL}/{cat}" if page_num == 1 else f"{BASE_URL}/{cat}/{page_num}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                except PWTimeout:
                    log(f"    ⚠ Timeout en {url}, saltando...")
                    break

                # Extraer productos de la página de listado
                productos = await page.evaluate("""
                    () => {
                        const result = [];
                        // Selectores comunes de cards de producto
                        const cards = document.querySelectorAll(
                            '.product-item, .product-thumb, .product-card, ' +
                            '[class*="product-item"], [class*="product_item"]'
                        );
                        cards.forEach(card => {
                            const linkEl   = card.querySelector('a[href*="/producto/"]');
                            const nameEl   = card.querySelector('[class*="name"], [class*="title"], h2, h3, h4');
                            const priceEl  = card.querySelector('[class*="price"], [class*="precio"], .price');
                            const skuEl    = card.querySelector('[class*="sku"], [class*="SKU"]');

                            if (!linkEl || !nameEl) return;

                            const href   = linkEl.href;
                            const parts  = href.split('/');
                            const id     = parts[parts.length - 1];
                            const nombre = nameEl.innerText.trim();
                            const precio = priceEl ? priceEl.innerText.trim() : null;
                            const sku    = skuEl   ? skuEl.innerText.replace(/sku:?\\s*/i,'').trim() : null;

                            if (nombre && id) result.push({ id, sku, nombre, precio, href });
                        });
                        return result;
                    }
                """)

                if not productos:
                    # Intentar obtener precios entrando al detalle de cada producto
                    # (solo si no los encontramos en el listado)
                    links = await page.evaluate("""
                        () => [...document.querySelectorAll('a[href*="/producto/"]')]
                              .map(a => ({ href: a.href, text: a.innerText.trim() }))
                              .filter(x => x.href.match(/\\/\\d+$/))
                              .slice(0, 30)
                    """)

                    for lnk in links:
                        try:
                            ppage = await ctx.new_page()
                            await ppage.goto(lnk["href"], wait_until="domcontentloaded", timeout=15000)
                            prod = await ppage.evaluate("""
                                () => {
                                    const nameEl  = document.querySelector('h1, [class*="product-name"]');
                                    const priceEl = document.querySelector('[class*="price"], [class*="precio"]');
                                    const skuEl   = document.querySelector('[class*="sku"]');
                                    const parts   = window.location.href.split('/');
                                    return {
                                        id     : parts[parts.length - 1],
                                        sku    : skuEl   ? skuEl.innerText.replace(/sku:?\\s*/i,'').trim() : null,
                                        nombre : nameEl  ? nameEl.innerText.trim() : null,
                                        precio : priceEl ? priceEl.innerText.trim() : null,
                                        href   : window.location.href
                                    };
                                }
                            """)
                            await ppage.close()
                            if prod.get("nombre"):
                                productos.append(prod)
                        except Exception:
                            pass

                if not productos:
                    break  # No hay más páginas

                # Guardar en DB
                cur = conn.cursor()
                for p in productos:
                    precio_val = parse_precio(p.get("precio") or "")
                    cur.execute("""
                        INSERT OR REPLACE INTO productos
                            (id, sku, nombre, precio, categoria, url, actualizado)
                        VALUES (?,?,?,?,?,?,?)
                    """, (p["id"], p.get("sku"), p["nombre"],
                          precio_val, cat, p.get("href"), now))
                conn.commit()
                total += len(productos)
                log(f"    Página {page_num}: {len(productos)} productos (total {total})")

                # ¿Hay página siguiente?
                has_next = await page.evaluate("""
                    () => {
                        const next = document.querySelector(
                            'a[rel="next"], .pagination .next:not(.disabled), a.page-next'
                        );
                        return !!next;
                    }
                """)
                if not has_next:
                    break
                page_num += 1

        # Registrar fecha de actualización
        conn.execute("""
            INSERT OR REPLACE INTO ultima_actualizacion (id, fecha) VALUES (1, ?)
        """, (now,))
        conn.commit()

        await browser.close()

    conn.close()
    log(f"\n✅ Listo: {total} productos guardados en base de datos.")
    return total


def _norm(s) -> str:
    """Elimina acentos y convierte a minúsculas para búsqueda. Tolera None."""
    import unicodedata
    if not s:
        return ""
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode("ascii")


def buscar_productos(query: str, categoria: str = "", limit: int = 100):
    conn = sqlite3.connect(DB_PATH)
    # Función personalizada que SQLite puede usar en los WHERE
    conn.create_function("norm", 1, _norm)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Cada palabra del query debe aparecer en nombre o SKU (sin importar acentos)
    palabras = [_norm(p) for p in query.split() if p.strip()]

    condiciones = " AND ".join(["(norm(nombre) LIKE ? OR norm(sku) LIKE ?)"] * len(palabras))
    params = []
    for p in palabras:
        params += [f"%{p}%", f"%{p}%"]

    sql = f"SELECT * FROM productos WHERE {condiciones}"

    if categoria and categoria != "Todas":
        sql += " AND categoria = ?"
        params.append(categoria.lower())

    sql += " ORDER BY nombre LIMIT ?"
    params.append(limit)

    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def importar_json(datos: list[dict]) -> int:
    """Actualiza precios desde JSON. Solo modifica productos existentes por SKU."""
    conn = init_db()
    now  = datetime.now().isoformat(timespec="seconds")
    cur  = conn.cursor()
    actualizados = 0
    for p in datos:
        precio_val = p.get("precio")
        if isinstance(precio_val, str):
            precio_val = parse_precio(precio_val)
        sku = p.get("sku")
        if not sku:
            continue
        rows = cur.execute("SELECT id FROM productos WHERE sku = ?", (sku,)).fetchall()
        for (prod_id,) in rows:
            cur.execute(
                "UPDATE productos SET precio=?, url=?, actualizado=? WHERE id=?",
                (precio_val, p.get("url"), now, prod_id),
            )
            actualizados += 1
    conn.execute("INSERT OR REPLACE INTO ultima_actualizacion (id, fecha) VALUES (1, ?)", (now,))
    conn.commit()
    conn.close()
    return actualizados


def ultima_actualizacion() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT fecha FROM ultima_actualizacion WHERE id=1").fetchone()
        conn.close()
        return row[0] if row else "Nunca"
    except Exception:
        return "Nunca"


def total_productos() -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        n = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Uso: python scraper.py <email> <password>")
        sys.exit(1)
    asyncio.run(scrape(sys.argv[1], sys.argv[2]))
