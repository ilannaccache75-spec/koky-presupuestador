"""
Generador de presupuestos PDF — identidad visual Librería KOKY.
Rojo #CC1515 · Amarillo dorado #F5C800 · Blanco · Negro carbón.
"""
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable, Image, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

# ── Paleta Koky ───────────────────────────────────────────────────────────────
ROJO        = colors.HexColor("#CC1515")   # rojo principal
ROJO_OSC    = colors.HexColor("#A31010")   # rojo oscuro (sombra/hover)
AMARILLO    = colors.HexColor("#F5C800")   # dorado Koky
AMARILLO_C  = colors.HexColor("#FFF4CC")   # amarillo muy claro (fila total)
CARBON      = colors.HexColor("#1A1A1A")   # texto principal
GRIS        = colors.HexColor("#5A5A5A")   # texto secundario
GRIS_LINEA  = colors.HexColor("#E0E0E0")   # separadores
FILA_PAR    = colors.HexColor("#FFFFFF")   # filas pares
FILA_IMPAR  = colors.HexColor("#FFF8F8")   # filas impares (sutilísimo rojo)
BLANCO      = colors.white

W, H = A4


def _E():
    def s(name, **kw):
        return ParagraphStyle(name, **kw)
    return {
        # Membrete
        "emp_nombre": s("emp_nombre", fontName="Helvetica-Bold",    fontSize=22, textColor=BLANCO, leading=26),
        "emp_slogan": s("emp_slogan", fontName="Helvetica-Oblique", fontSize=9,  textColor=AMARILLO, leading=13),
        # Etiquetas meta
        "meta_label": s("meta_label", fontName="Helvetica-Bold",    fontSize=7,  textColor=GRIS,
                        charSpace=1.5, leading=10),
        "meta_valor": s("meta_valor", fontName="Helvetica",          fontSize=10.5, textColor=CARBON, leading=14),
        "num_presup": s("num_presup", fontName="Helvetica-Bold",    fontSize=18, textColor=ROJO,
                        alignment=TA_RIGHT, leading=22),
        "validez":    s("validez",    fontName="Helvetica",          fontSize=10, textColor=CARBON,
                        alignment=TA_RIGHT, leading=13),
        # Cabecera tabla
        "th":         s("th",         fontName="Helvetica-Bold",    fontSize=8,  textColor=BLANCO,
                        charSpace=0.5, alignment=TA_CENTER, leading=10),
        # Celdas tabla
        "td_left":    s("td_left",    fontName="Helvetica",          fontSize=9,  textColor=CARBON,  leading=11),
        "td_sku":     s("td_sku",     fontName="Helvetica",          fontSize=7.5, textColor=GRIS,   alignment=TA_CENTER, leading=10),
        "td_cant":    s("td_cant",    fontName="Helvetica-Bold",    fontSize=10, textColor=CARBON,  alignment=TA_CENTER, leading=12),
        "td_price":   s("td_price",   fontName="Helvetica",          fontSize=9,  textColor=CARBON,  alignment=TA_RIGHT,  leading=11),
        "td_sub":     s("td_sub",     fontName="Helvetica-Bold",    fontSize=9,  textColor=CARBON,  alignment=TA_RIGHT,  leading=11),
        # Totales
        "tot_label":  s("tot_label",  fontName="Helvetica",          fontSize=8.5, textColor=GRIS,   charSpace=0.5, alignment=TA_RIGHT, leading=12),
        "tot_valor":  s("tot_valor",  fontName="Helvetica",          fontSize=9,   textColor=CARBON, alignment=TA_RIGHT, leading=12),
        "tot_fin_l":  s("tot_fin_l",  fontName="Helvetica-Bold",    fontSize=11,  textColor=CARBON,
                        charSpace=0.3, alignment=TA_RIGHT, leading=14),
        "tot_fin_v":  s("tot_fin_v",  fontName="Helvetica-Bold",    fontSize=14,  textColor=CARBON, alignment=TA_RIGHT, leading=17),
        # Notas / pie
        "nota_h":     s("nota_h",     fontName="Helvetica-Bold",    fontSize=8,  textColor=ROJO,   charSpace=1.5, leading=10),
        "nota_b":     s("nota_b",     fontName="Helvetica-Oblique", fontSize=8.5, textColor=GRIS,  leading=12),
        "pie":        s("pie",        fontName="Helvetica",          fontSize=7,  textColor=GRIS,  alignment=TA_CENTER, leading=10),
    }


def _ar(val: float) -> str:
    """Formato argentino: $ 1.234,56"""
    partes = f"{val:,.2f}".split(".")
    entero = partes[0].replace(",", ".")
    return f"$ {entero},{partes[1]}"


def generar_pdf(
    items: list[dict],
    markup_pct: float,
    empresa: str,
    cliente: str,
    numero: int,
    notas: str = "",
    logo_path: "str | Path | None" = None,
    destino: "Path | None" = None,
    iva_modo: str = "Sin IVA",
) -> Path:
    if destino is None:
        carpeta = Path(__file__).parent.parent / "Presupuestos"
        carpeta.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^\w]", "_", cliente)
        destino = carpeta / f"Presupuesto_{numero:05d}_{slug}.pdf"

    doc = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        leftMargin=0, rightMargin=0,
        topMargin=0,  bottomMargin=0,
    )

    E     = _E()
    story = []
    PAD   = 1.8 * cm          # margen lateral interno
    ANCHO = W - 2 * PAD       # ancho útil del contenido

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE ROJO: header con logo a la izquierda, nombre empresa a la derecha
    # ══════════════════════════════════════════════════════════════════════════
    logo_img = None
    if logo_path and Path(logo_path).exists():
        try:
            logo_img = Image(str(logo_path), width=3.6*cm, height=2.4*cm, kind="proportional")
        except Exception:
            logo_img = None

    nombre_p = Paragraph(empresa, E["emp_nombre"])
    slogan_p = Paragraph("Siempre útiles · Mayorista", E["emp_slogan"])

    if logo_img:
        hdr_data = [[ logo_img, [nombre_p, Spacer(1, 3), slogan_p] ]]
        hdr_cols = [4*cm, ANCHO - 4*cm]
    else:
        hdr_data = [[ [nombre_p, Spacer(1, 3), slogan_p], "" ]]
        hdr_cols = [ANCHO * 0.65, ANCHO * 0.35]

    hdr_inner = Table(hdr_data, colWidths=hdr_cols)
    hdr_inner.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # Wrapper rojo a ancho completo de página
    hdr_full = Table(
        [[hdr_inner]],
        colWidths=[W],
    )
    hdr_full.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), ROJO),
        ("LEFTPADDING",   (0, 0), (-1, -1), PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), PAD),
        ("TOPPADDING",    (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(hdr_full)

    # Franja amarilla delgada (como el acento del logo)
    amarillo_strip = Table([[""]],  colWidths=[W])
    amarillo_strip.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), AMARILLO),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(amarillo_strip)

    # ══════════════════════════════════════════════════════════════════════════
    # METADATOS: cliente / fecha  |  N° presupuesto / validez
    # ══════════════════════════════════════════════════════════════════════════
    fecha = datetime.now().strftime("%d / %m / %Y")

    meta_izq = Table([
        [Paragraph("CLIENTE", E["meta_label"])],
        [Paragraph(cliente or "—", E["meta_valor"])],
        [Spacer(1, 6)],
        [Paragraph("FECHA", E["meta_label"])],
        [Paragraph(fecha, E["meta_valor"])],
    ], colWidths=[ANCHO * 0.55])
    meta_izq.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))

    meta_der = Table([
        [Paragraph("PRESUPUESTO N°", E["meta_label"])],
        [Paragraph(f"{numero:05d}", E["num_presup"])],
        [Spacer(1, 6)],
        [Paragraph("VALIDEZ", E["meta_label"])],
        [Paragraph("48 horas", E["validez"])],
    ], colWidths=[ANCHO * 0.45])
    meta_der.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
    ]))

    meta_row = Table([[meta_izq, meta_der]], colWidths=[ANCHO * 0.55, ANCHO * 0.45])
    meta_row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    meta_wrap = Table([[meta_row]], colWidths=[W])
    meta_wrap.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), PAD),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, GRIS_LINEA),
    ]))
    story.append(meta_wrap)

    # ══════════════════════════════════════════════════════════════════════════
    # TABLA DE PRODUCTOS
    # ══════════════════════════════════════════════════════════════════════════
    col_w = [
        ANCHO * 0.06,   # Cant
        ANCHO * 0.09,   # SKU
        ANCHO * 0.46,   # Descripción
        ANCHO * 0.19,   # Precio unitario
        ANCHO * 0.20,   # Subtotal
    ]

    encabezados = [
        Paragraph("CANT", E["th"]),
        Paragraph("SKU",  E["th"]),
        Paragraph("DESCRIPCIÓN", E["th"]),
        Paragraph("PRECIO UNIT.", E["th"]),
        Paragraph("SUBTOTAL", E["th"]),
    ]

    filas_data   = []
    filas_fondo  = []
    total_general = 0.0

    for i, item in enumerate(items):
        mkp      = item.get("markup", markup_pct)   # % propio del ítem, o el global
        pv       = item.get("precio_custom") or item["precio_costo"] * (1 + mkp / 100)
        subtotal = pv * item["cantidad"]
        total_general += subtotal

        nombre_pdf = item.get("nombre_custom") or item["nombre"]
        filas_data.append([
            Paragraph(str(item["cantidad"]),        E["td_cant"]),
            Paragraph(str(item.get("sku") or "—"), E["td_sku"]),
            Paragraph(nombre_pdf,                   E["td_left"]),
            Paragraph(_ar(pv),                     E["td_price"]),
            Paragraph(_ar(subtotal),               E["td_sub"]),
        ])
        filas_fondo.append(FILA_PAR if i % 2 == 0 else FILA_IMPAR)

    tabla_datos = [encabezados] + filas_data

    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), ROJO),          # cabecera roja
        ("TOPPADDING",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.25, GRIS_LINEA),
        ("BOX",           (0, 0), (-1, -1), 0.5,  GRIS_LINEA),
    ])
    for i, fondo in enumerate(filas_fondo, 1):
        ts.add("BACKGROUND", (0, i), (-1, i), fondo)

    prod_tbl = Table(tabla_datos, colWidths=col_w, repeatRows=1)
    prod_tbl.setStyle(ts)

    tabla_wrap = Table([[prod_tbl]], colWidths=[W])
    tabla_wrap.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), PAD),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(tabla_wrap)

    # ══════════════════════════════════════════════════════════════════════════
    # BLOQUE DE TOTALES
    # ══════════════════════════════════════════════════════════════════════════
    if iva_modo == "+ IVA 21%":
        iva_monto   = total_general * 0.21
        total_final = total_general + iva_monto
        tot_data = [
            ["", Paragraph("SUBTOTAL",        E["tot_label"]), Paragraph(_ar(total_general), E["tot_valor"])],
            ["", Paragraph("IVA 21%",         E["tot_label"]), Paragraph(_ar(iva_monto),     E["tot_valor"])],
            ["", Paragraph("TOTAL A COBRAR",  E["tot_fin_l"]), Paragraph(_ar(total_final),   E["tot_fin_v"])],
        ]
        tot_style = [
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS",(0, 0), (-1, 1), [FILA_PAR, FILA_IMPAR]),
            ("BACKGROUND",    (0, 2), (-1, 2), AMARILLO),
            ("FONT",          (0, 2), (-1, 2), "Helvetica-Bold"),
            ("TOPPADDING",    (0, 2), (-1, 2), 9),
            ("BOTTOMPADDING", (0, 2), (-1, 2), 9),
            ("LINEABOVE",     (0, 2), (-1, 2), 2, ROJO),
            ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_LINEA),
        ]
    elif iva_modo == "IVA incluido":
        total_final = total_general
        tot_data = [
            ["", Paragraph("TOTAL A COBRAR\n(IVA incluido)", E["tot_fin_l"]), Paragraph(_ar(total_final), E["tot_fin_v"])],
        ]
        tot_style = [
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("BACKGROUND",    (0, 0), (-1, 0), AMARILLO),
            ("FONT",          (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEABOVE",     (0, 0), (-1, 0), 2, ROJO),
            ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_LINEA),
        ]
    else:  # Sin IVA
        total_final = total_general
        tot_data = [
            ["", Paragraph("TOTAL A COBRAR", E["tot_fin_l"]), Paragraph(_ar(total_final), E["tot_fin_v"])],
        ]
        tot_style = [
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("BACKGROUND",    (0, 0), (-1, 0), AMARILLO),
            ("FONT",          (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEABOVE",     (0, 0), (-1, 0), 2, ROJO),
            ("BOX",           (0, 0), (-1, -1), 0.5, GRIS_LINEA),
        ]

    tot_tbl = Table(tot_data, colWidths=[ANCHO * 0.55, ANCHO * 0.26, ANCHO * 0.19])
    tot_tbl.setStyle(TableStyle(tot_style))

    tot_wrap = Table([[tot_tbl]], colWidths=[W])
    tot_wrap.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), PAD),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(tot_wrap)

    # ══════════════════════════════════════════════════════════════════════════
    # NOTAS
    # ══════════════════════════════════════════════════════════════════════════
    if notas.strip():
        nota_inner = Table([
            [Paragraph("CONDICIONES Y NOTAS", E["nota_h"])],
            [Paragraph(notas, E["nota_b"])],
        ], colWidths=[ANCHO])
        nota_inner.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ("LINEBEFORE",    (0, 0), (-1, -1), 4, ROJO),   # borde rojo izquierdo
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FFF8F8")),
            ("BOX",           (0, 0), (-1, -1), 0.3, GRIS_LINEA),
        ]))
        nota_wrap = Table([[nota_inner]], colWidths=[W])
        nota_wrap.setStyle(TableStyle([
            ("LEFTPADDING",   (0, 0), (-1, -1), PAD),
            ("RIGHTPADDING",  (0, 0), (-1, -1), PAD),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(nota_wrap)

    # ══════════════════════════════════════════════════════════════════════════
    # PIE — franja roja final
    # ══════════════════════════════════════════════════════════════════════════
    pie_p = Paragraph(
        f"<b>{empresa.upper()}</b>  ·  Presupuesto N° {numero:05d}  ·  Válido 48 hs.  ·  {fecha}",
        E["pie"]
    )
    # Spacer flexible para empujar el pie hacia el fondo
    story.append(Spacer(1, 30))

    pie_strip = Table([[pie_p]], colWidths=[W])
    pie_strip.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), ROJO),
        ("LEFTPADDING",   (0, 0), (-1, -1), PAD),
        ("RIGHTPADDING",  (0, 0), (-1, -1), PAD),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    # Franja amarilla cierre
    pie_amarillo = Table([[""]],  colWidths=[W])
    pie_amarillo.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), AMARILLO),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(pie_strip)
    story.append(pie_amarillo)

    doc.build(story)
    return destino
