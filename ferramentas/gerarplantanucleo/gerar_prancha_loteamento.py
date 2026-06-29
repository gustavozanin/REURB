# -*- coding: utf-8 -*-

import math
import os
import struct
from collections import Counter
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


STATUS_LEGENDA = {
    0: ("Sem status", colors.HexColor("#E6E6E6")),
    1: ("Concluída no ponto fixo", colors.HexColor("#2E7D32")),
    2: ("Em andamento", colors.HexColor("#F9A825")),
    3: ("Aguardando início", colors.HexColor("#90CAF9")),
    4: ("Concluída em campo", colors.HexColor("#66BB6A")),
    5: ("Litígio", colors.HexColor("#8E24AA")),
    6: ("Pendente de confirmação", colors.HexColor("#FFB74D")),
    7: ("Área Rural", colors.HexColor("#9CCC65")),
    8: ("Cancelado", colors.HexColor("#EF5350")),
    9: ("Terreno", colors.HexColor("#BDBDBD")),
    10: ("Faixa de Domínio", colors.HexColor("#90A4AE")),
    11: ("Alagado", colors.HexColor("#4FC3F7")),
}

BRASAO_CANDIDATOS = [
    Path(r"C:\Users\gusta\Downloads\Brasão_do_Maranhão.png"),
    Path(r"C:\Users\gusta\Downloads\BrasÃ£o_do_MaranhÃ£o.png"),
]
LOGO_CANDIDATOS = [
    Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_Maranhão_(2023-2027).png"),
    Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_MaranhÃ£o_(2023-2027).png"),
]


def _logo_existente(candidatos):
    for caminho in candidatos:
        if caminho.exists():
            return str(caminho)
    return None


def _slug(texto):
    import unicodedata

    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    texto = "".join(char.lower() if char.isalnum() else "_" for char in texto)
    while "__" in texto:
        texto = texto.replace("__", "_")
    return texto.strip("_") or "bairro"


def _ler_dbf(base):
    dbf_path = Path(str(base) + ".dbf")
    cpg_path = Path(str(base) + ".cpg")
    encoding = cpg_path.read_text(errors="ignore").strip() if cpg_path.exists() else "utf-8"
    encoding = encoding or "utf-8"
    data = dbf_path.read_bytes()
    quantidade = struct.unpack("<I", data[4:8])[0]
    header_len = struct.unpack("<H", data[8:10])[0]
    record_len = struct.unpack("<H", data[10:12])[0]

    campos = []
    pos = 32
    while pos < len(data) and data[pos] != 0x0D:
        nome = data[pos:pos + 11].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
        tamanho = data[pos + 16]
        campos.append((nome, tamanho))
        pos += 32

    registros = []
    offset = header_len
    for _ in range(quantidade):
        record = data[offset:offset + record_len]
        offset += record_len
        if not record or record[0:1] == b"*":
            continue
        ponteiro = 1
        row = {}
        for nome, tamanho in campos:
            raw = record[ponteiro:ponteiro + tamanho]
            ponteiro += tamanho
            row[nome] = raw.decode(encoding, errors="replace").strip()
        registros.append(row)
    return registros


def _ler_poligonos(base):
    shp_path = Path(str(base) + ".shp")
    data = shp_path.read_bytes()
    offset = 100
    shapes = []
    while offset + 8 <= len(data):
        _, record_len_words = struct.unpack(">2i", data[offset:offset + 8])
        content_start = offset + 8
        content = data[content_start:content_start + record_len_words * 2]
        if len(content) < 44:
            break
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type == 5:
            n_parts = struct.unpack("<i", content[36:40])[0]
            n_points = struct.unpack("<i", content[40:44])[0]
            parts = list(struct.unpack("<" + "i" * n_parts, content[44:44 + 4 * n_parts]))
            points_offset = 44 + 4 * n_parts
            points = [
                struct.unpack("<2d", content[points_offset + i * 16:points_offset + i * 16 + 16])
                for i in range(n_points)
            ]
            rings = []
            for idx, start in enumerate(parts):
                end = parts[idx + 1] if idx + 1 < len(parts) else len(points)
                rings.append(points[start:end])
            shapes.append(rings)
        offset = content_start + record_len_words * 2
    return shapes


def _utm_23s(lon, lat):
    a = 6378137.0
    f = 1 / 298.257222101
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996
    lon0 = math.radians(-45)
    fe = 500000
    fn = 10000000
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = ep2 * math.cos(lat_rad) ** 2
    aa = math.cos(lat_rad) * (lon_rad - lon0)
    m = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * lat_rad
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * lat_rad)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * lat_rad)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * lat_rad)
    )
    x = fe + k0 * n * (aa + (1 - t + c) * aa ** 3 / 6 + (5 - 18 * t + t ** 2 + 72 * c - 58 * ep2) * aa ** 5 / 120)
    y = fn + k0 * (m + n * math.tan(lat_rad) * (aa ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * aa ** 4 / 24 + (61 - 58 * t + t ** 2 + 600 * c - 330 * ep2) * aa ** 6 / 720))
    return x, y


def _area_centroide(ring):
    area = 0
    cx = 0
    cy = 0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < 1e-12:
        return 0, (sum(x for x, _ in ring) / len(ring), sum(y for _, y in ring) / len(ring))
    area *= 0.5
    return abs(area), (cx / (6 * area), cy / (6 * area))


def _carregar_lotes(shp_path):
    base = Path(shp_path).with_suffix("")
    registros = _ler_dbf(base)
    shapes = _ler_poligonos(base)
    lotes = []
    for row, rings_lonlat in zip(registros, shapes):
        rings_utm = [[_utm_23s(lon, lat) for lon, lat in ring] for ring in rings_lonlat]
        area, centro = _area_centroide(rings_utm[0])
        try:
            status = int(float(row.get("status") or 0))
        except Exception:
            status = 0
        lotes.append({
            "row": row,
            "rings": rings_utm,
            "status": status,
            "area": area,
            "centro": centro,
        })
    return lotes


def _bounds(lotes):
    xs = []
    ys = []
    for lote in lotes:
        for ring in lote["rings"]:
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _draw_logo(c, path, x, y, w, h):
    if path:
        try:
            c.drawImage(path, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass


def _draw_header(c, page_w, page_h, titulo, subtitulo):
    brasao = _logo_existente(BRASAO_CANDIDATOS)
    logo = _logo_existente(LOGO_CANDIDATOS)
    y = page_h - 2.1 * cm
    _draw_logo(c, brasao, 1.5 * cm, y - 0.15 * cm, 1.25 * cm, 1.25 * cm)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2.9 * cm, y + 0.45 * cm, "GOVERNO DO ESTADO DO MARANHÃO")
    c.setFont("Helvetica", 7.5)
    c.drawString(2.9 * cm, y + 0.08 * cm, "INSTITUTO DE COLONIZAÇÃO E TERRAS DO MARANHÃO - ITERMA")
    _draw_logo(c, logo, page_w - 7.3 * cm, y - 0.05 * cm, 3.2 * cm, 1.1 * cm)
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(page_w - 1.5 * cm, y + 0.28 * cm, "ITERMA")
    c.line(1.5 * cm, y - 0.35 * cm, page_w - 1.5 * cm, y - 0.35 * cm)

    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(page_w / 2, y - 1.05 * cm, titulo)
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(page_w / 2, y - 1.45 * cm, subtitulo)


def _draw_north_arrow(c, x, y):
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.black)
    c.line(x, y, x, y + 1.2 * cm)
    c.line(x, y + 1.2 * cm, x - 0.12 * cm, y + 0.9 * cm)
    c.line(x, y + 1.2 * cm, x + 0.12 * cm, y + 0.9 * cm)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(x, y + 1.35 * cm, "N")


def _draw_scale_bar(c, x, y, metres_to_pt, comprimento_m=200):
    largura = comprimento_m * metres_to_pt
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.line(x, y, x + largura, y)
    for i in range(5):
        xi = x + largura * i / 4
        c.line(xi, y - 0.08 * cm, xi, y + 0.08 * cm)
        c.setFont("Helvetica", 5.5)
        c.drawCentredString(xi, y - 0.25 * cm, str(int(comprimento_m * i / 4)))
    c.drawCentredString(x + largura, y - 0.25 * cm, f"{comprimento_m} m")


def _draw_map(c, lotes, x0, y0, w, h):
    minx, miny, maxx, maxy = _bounds(lotes)
    padx = (maxx - minx) * 0.08
    pady = (maxy - miny) * 0.08
    minx -= padx
    maxx += padx
    miny -= pady
    maxy += pady
    sx = w / (maxx - minx)
    sy = h / (maxy - miny)
    scale = min(sx, sy)
    map_w = (maxx - minx) * scale
    map_h = (maxy - miny) * scale
    ox = x0 + (w - map_w) / 2
    oy = y0 + (h - map_h) / 2

    def tr(pt):
        x, y = pt
        return ox + (x - minx) * scale, oy + (y - miny) * scale

    c.setStrokeColor(colors.HexColor("#444444"))
    c.setFillColor(colors.white)
    c.rect(x0, y0, w, h, stroke=1, fill=0)

    grid_step = 200
    gx0 = math.ceil(minx / grid_step) * grid_step
    gy0 = math.ceil(miny / grid_step) * grid_step
    c.setStrokeColor(colors.HexColor("#E0E0E0"))
    c.setLineWidth(0.25)
    c.setFont("Helvetica", 4.8)
    gx = gx0
    while gx <= maxx:
        px, _ = tr((gx, miny))
        c.line(px, y0, px, y0 + h)
        c.drawCentredString(px, y0 - 0.16 * cm, f"{int(gx)}")
        gx += grid_step
    gy = gy0
    while gy <= maxy:
        _, py = tr((minx, gy))
        c.line(x0, py, x0 + w, py)
        c.saveState()
        c.translate(x0 - 0.18 * cm, py)
        c.rotate(90)
        c.drawCentredString(0, 0, f"{int(gy)}")
        c.restoreState()
        gy += grid_step

    for lote in lotes:
        nome_status, cor = STATUS_LEGENDA.get(lote["status"], STATUS_LEGENDA[0])
        c.setFillColor(cor)
        c.setStrokeColor(colors.HexColor("#333333"))
        c.setLineWidth(0.25)
        for ring in lote["rings"]:
            path = c.beginPath()
            first = True
            for pt in ring:
                px, py = tr(pt)
                if first:
                    path.moveTo(px, py)
                    first = False
                else:
                    path.lineTo(px, py)
            path.close()
            c.drawPath(path, stroke=1, fill=1)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 3.5)
    for lote in lotes:
        if lote["area"] < 120:
            continue
        px, py = tr(lote["centro"])
        row = lote["row"]
        label = f"Q{row.get('quadra', '')}-L{row.get('lote', '')}"
        c.drawCentredString(px, py - 1.7, label)

    _draw_north_arrow(c, x0 + w - 0.7 * cm, y0 + h - 1.6 * cm)
    _draw_scale_bar(c, x0 + 0.55 * cm, y0 + 0.45 * cm, scale, 200)
    c.setFont("Helvetica", 6)
    c.drawRightString(x0 + w - 0.4 * cm, y0 + 0.35 * cm, "SIRGAS 2000 / UTM 23S")


def _draw_legend_and_stamp(c, lotes, x, y, w, h, municipio, bairro, numero):
    c.setStrokeColor(colors.HexColor("#555555"))
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 0.25 * cm, y + h - 0.45 * cm, "Legenda - Status dos Lotes")

    status_counts = Counter(lote["status"] for lote in lotes)
    yy = y + h - 0.8 * cm
    for status, (label, cor) in STATUS_LEGENDA.items():
        c.setFillColor(cor)
        c.rect(x + 0.25 * cm, yy - 0.12 * cm, 0.22 * cm, 0.22 * cm, stroke=1, fill=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 5.9)
        c.drawString(x + 0.58 * cm, yy - 0.08 * cm, f"{status} - {label} ({status_counts.get(status, 0)})")
        yy -= 0.30 * cm

    yy -= 0.15 * cm
    c.line(x, yy, x + w, yy)
    yy -= 0.38 * cm
    c.setFont("Helvetica-Bold", 7)
    c.drawString(x + 0.25 * cm, yy, "Dados da Prancha")
    c.setFont("Helvetica", 6.0)
    dados = [
        ("Município", municipio),
        ("Bairro", bairro),
        ("Processo", numero),
        ("Total de lotes", str(len(lotes))),
        ("Beneficiários listados", str(sum(1 for lote in lotes if lote["status"] in (1, 4)))),
        ("Sistema", "SIRGAS 2000 / UTM 23S"),
    ]
    yy -= 0.35 * cm
    for chave, valor in dados:
        c.setFont("Helvetica-Bold", 6.0)
        c.drawString(x + 0.25 * cm, yy, f"{chave}:")
        c.setFont("Helvetica", 6.0)
        c.drawString(x + 3.15 * cm, yy, str(valor))
        yy -= 0.32 * cm


def _pagina_mapa(c, lotes, municipio, bairro, numero):
    page_w, page_h = landscape(A3)
    titulo = f"PRANCHA 02 - PLANTA DO LOTEAMENTO - {municipio.upper()} - {bairro.upper()}"
    subtitulo = "Planta georreferenciada dos lotes e status cadastral"
    _draw_header(c, page_w, page_h, titulo, subtitulo)

    margin = 1.5 * cm
    map_x = margin
    map_y = 2.1 * cm
    map_w = page_w - 10.1 * cm
    map_h = page_h - 5.4 * cm
    _draw_map(c, lotes, map_x, map_y, map_w, map_h)
    _draw_legend_and_stamp(
        c,
        lotes,
        map_x + map_w + 0.45 * cm,
        map_y,
        page_w - map_x - map_w - margin - 0.45 * cm,
        map_h,
        municipio,
        bairro,
        numero,
    )

    c.setFont("Helvetica", 5.8)
    c.drawString(margin, 1.35 * cm, "Fonte: shapefile de lotes informado. Lista de Beneficiários considera somente status 1 e 4.")
    c.showPage()


def _linhas_beneficiarios(lotes):
    linhas = []
    for lote in lotes:
        if lote["status"] not in (1, 4):
            continue
        row = lote["row"]
        status_nome = STATUS_LEGENDA.get(lote["status"], STATUS_LEGENDA[0])[0]
        linhas.append([
            row.get("quadra", ""),
            row.get("lote", ""),
            row.get("nome", "") or "NÃO INFORMADO",
            row.get("cpf_cnpj", "") or "",
            f"{lote['status']} - {status_nome}",
        ])
    return sorted(linhas, key=lambda item: (int(item[0]) if str(item[0]).isdigit() else 9999, str(item[1])))


def _gerar_lista_beneficiarios(out_path, lotes, municipio, bairro, numero):
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=landscape(A3),
        leftMargin=1.25 * cm,
        rightMargin=1.25 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )
    styles = {
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=13, leading=15, alignment=TA_CENTER),
        "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=8, leading=10, alignment=TA_CENTER),
        "normal": ParagraphStyle("normal", fontName="Helvetica", fontSize=6.4, leading=7.4, alignment=TA_LEFT),
    }
    linhas = _linhas_beneficiarios(lotes)
    data = [["Quadra", "Lote", "Nome do interessado", "CPF/CNPJ", "Status"]]
    for linha in linhas:
        data.append([Paragraph(str(valor), styles["normal"]) for valor in linha])

    story = [
        Paragraph(f"LISTA DE BENEFICIÁRIOS - {bairro.upper()} - {municipio.upper()}", styles["titulo"]),
        Paragraph(f"Processo REURB Coletivo: {numero} | Filtro: status 1 e 4 | Total: {len(linhas)} beneficiários", styles["sub"]),
        Spacer(1, 0.25 * cm),
    ]
    tabela = Table(data, colWidths=[1.6 * cm, 1.7 * cm, 11.8 * cm, 4.0 * cm, 7.0 * cm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#777777")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9EAD3")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tabela)
    doc.build(story)


def gerar_prancha_loteamento(
    shp_lotes,
    numero_reurb_coletivo="051201571/2026",
    municipio="Peri Mirim",
    bairro="Campo de Pouso",
    pasta_resultados=None,
):
    lotes = _carregar_lotes(shp_lotes)
    nome_base = numero_reurb_coletivo.replace("/", "_")
    if pasta_resultados is None:
        pasta_resultados = Path(__file__).parent / "resultados" / f"{_slug(bairro)}_{nome_base}"
    pasta_resultados = Path(pasta_resultados)
    pasta_resultados.mkdir(parents=True, exist_ok=True)

    mapa_pdf = pasta_resultados / f"PRANCHA_02-_PLANTA_DO_LOTEAMENTO_{_slug(municipio).upper()}_{_slug(bairro).upper()}_mapa.pdf"
    lista_pdf = pasta_resultados / f"PRANCHA_02_LISTA_DE_BENEFICIARIOS_{_slug(municipio).upper()}_{_slug(bairro).upper()}.pdf"
    final_pdf = pasta_resultados / f"PRANCHA_02-_PLANTA_DO_LOTEAMENTO_{_slug(municipio).upper()}_{_slug(bairro).upper()}.pdf"

    c = canvas.Canvas(str(mapa_pdf), pagesize=landscape(A3))
    _pagina_mapa(c, lotes, municipio, bairro, numero_reurb_coletivo)
    c.save()
    _gerar_lista_beneficiarios(lista_pdf, lotes, municipio, bairro, numero_reurb_coletivo)

    try:
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        for caminho in [mapa_pdf, lista_pdf]:
            reader = PdfReader(str(caminho))
            for page in reader.pages:
                writer.add_page(page)
        with open(final_pdf, "wb") as arquivo:
            writer.write(arquivo)
    except Exception:
        final_pdf = mapa_pdf

    return str(final_pdf)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gera Prancha 02 - Planta do Loteamento e Lista de Beneficiários.")
    parser.add_argument("--shp", default=r"C:\REURB\SHP\lotes_051201571_2026.shp")
    parser.add_argument("--numero", default="051201571/2026")
    parser.add_argument("--municipio", default="Peri Mirim")
    parser.add_argument("--bairro", default="Campo de Pouso")
    parser.add_argument("--saida", default=None)
    args = parser.parse_args()
    print(gerar_prancha_loteamento(args.shp, args.numero, args.municipio, args.bairro, args.saida))
