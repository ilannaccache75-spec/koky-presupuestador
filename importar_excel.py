"""
Importa la lista de precios descargada de papelerabariloche.com.ar al DB.
Aplica el descuento de cuenta (4%) al precio de lista con IVA.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "productos.db"
DESCUENTO = 0.04  # descuento de cuenta Koky


def importar(excel_path: str, descuento_pct: float = DESCUENTO, callback=None) -> dict:
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("Falta openpyxl: pip install openpyxl")

    def log(msg):
        if callback:
            callback(msg)
        else:
            print(msg)

    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb["Lista de Precios"]

    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat(timespec="seconds")

    actualizados = 0
    insertados = 0
    sin_precio = 0
    factor = 1 - descuento_pct / 100

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 10:
            continue  # saltar encabezados

        sku = str(row[1] or "").strip()
        nombre = str(row[2] or "").strip()
        precio_lista = row[3]  # PRECIO CON IVA
        clasificacion = str(row[11] or "").strip()

        if not nombre or not precio_lista:
            sin_precio += 1
            continue
        try:
            precio_lista = float(precio_lista)
        except (TypeError, ValueError):
            sin_precio += 1
            continue
        if precio_lista <= 0:
            sin_precio += 1
            continue

        precio = round(precio_lista * factor, 2)

        # Categoría: primer nivel de la clasificación
        categoria = clasificacion.split("/")[0].strip().lower() if clasificacion else ""

        # Buscar registro existente por SKU
        existing = None
        if sku:
            existing = conn.execute(
                "SELECT id FROM productos WHERE sku = ?", (sku,)
            ).fetchone()

        if existing:
            conn.execute(
                "UPDATE productos SET nombre=?, precio=?, categoria=?, actualizado=? WHERE sku=?",
                (nombre, precio, categoria, now, sku),
            )
            actualizados += 1

        if (actualizados + insertados) % 1000 == 0:
            log(f"  {actualizados + insertados} procesados...")
            conn.commit()

    conn.execute(
        "INSERT OR REPLACE INTO ultima_actualizacion (id, fecha) VALUES (1, ?)", (now,)
    )
    conn.commit()
    conn.close()
    wb.close()

    return {"actualizados": actualizados, "insertados": insertados, "sin_precio": sin_precio}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python importar_excel.py <ruta_excel> [descuento_pct]")
        sys.exit(1)
    pct = float(sys.argv[2]) if len(sys.argv) > 2 else DESCUENTO * 100
    resultado = importar(sys.argv[1], pct)
    print(f"✅ Actualizados: {resultado['actualizados']}, Insertados: {resultado['insertados']}, Sin precio: {resultado['sin_precio']}")
