# -*- coding: utf-8 -*-

import json
import math
import struct
import zipfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas


SHP = Path(r"C:\REURB\SHP\bairro_camada.shp")
PROCESSO = "051201571/2026"
BAIRRO = "CAMPO DE POUSO"
OUT_DIR = Path(__file__).parent.joinpath("resultados")

A = 6378137.0
F = 1 / 298.257222101
B = (1 - F) * A
E2 = F * (2 - F)
EP2 = E2 / (1 - E2)
K0 = 0.9996


def ler_dbf(dbf_path):
    data = dbf_path.read_bytes()
    nrec = struct.unpack("<I", data[4:8])[0]
    hlen = struct.unpack("<H", data[8:10])[0]
    rlen = struct.unpack("<H", data[10:12])[0]
    fields = []
    off = 32
    pos = 1
    while off < hlen - 1:
        desc = data[off:off + 32]
        name = desc[:11].split(b"\x00", 1)[0].decode("latin1")
        length = desc[16]
        fields.append((name, pos, length))
        pos += length
        off += 32

    rows = []
    for row_index in range(nrec):
        start = hlen + row_index * rlen
        if data[start:start + 1] == b"*":
            continue
        row = {}
        for name, field_start, length in fields:
            raw = data[start + field_start:start + field_start + length]
            row[name] = raw.decode("latin1").strip()
        rows.append(row)
    return rows


def ler_poligono(shp_path):
    data = shp_path.read_bytes()
    offset = 100
    pontos = []
    while offset < len(data):
        content_len_words = struct.unpack(">i", data[offset + 4:offset + 8])[0]
        content_start = offset + 8
        content_end = content_start + content_len_words * 2
        shape_type = struct.unpack("<i", data[content_start:content_start + 4])[0]
        if shape_type == 5:
            num_parts = struct.unpack("<i", data[content_start + 36:content_start + 40])[0]
            num_points = struct.unpack("<i", data[content_start + 40:content_start + 44])[0]
            parts_start = content_start + 44
            parts = [
                struct.unpack("<i", data[parts_start + i * 4:parts_start + i * 4 + 4])[0]
                for i in range(num_parts)
            ]
            points_start = parts_start + num_parts * 4
            all_points = []
            for i in range(num_points):
                x, y = struct.unpack("<dd", data[points_start + i * 16:points_start + i * 16 + 16])
                all_points.append((x, y))
            first_part_end = parts[1] if len(parts) > 1 else len(all_points)
            pontos = all_points[parts[0]:first_part_end]
            break
        offset = content_end

    if pontos and pontos[0] == pontos[-1]:
        pontos = pontos[:-1]
    return pontos


def utm_zone(lon):
    return int((lon + 180) / 6) + 1


def lonlat_para_utm(lon, lat, zone):
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    n = A / math.sqrt(1 - E2 * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = EP2 * math.cos(lat_rad) ** 2
    aa = math.cos(lat_rad) * (lon_rad - lon0)
    m = A * (
        (1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256) * lat_rad
        - (3 * E2 / 8 + 3 * E2 ** 2 / 32 + 45 * E2 ** 3 / 1024) * math.sin(2 * lat_rad)
        + (15 * E2 ** 2 / 256 + 45 * E2 ** 3 / 1024) * math.sin(4 * lat_rad)
        - (35 * E2 ** 3 / 3072) * math.sin(6 * lat_rad)
    )

    easting = K0 * n * (
        aa + (1 - t + c) * aa ** 3 / 6
        + (5 - 18 * t + t ** 2 + 72 * c - 58 * EP2) * aa ** 5 / 120
    ) + 500000

    northing = K0 * (
        m + n * math.tan(lat_rad) * (
            aa ** 2 / 2
            + (5 - t + 9 * c + 4 * c ** 2) * aa ** 4 / 24
            + (61 - 58 * t + t ** 2 + 600 * c - 330 * EP2) * aa ** 6 / 720
        )
    )
    if lat < 0:
        northing += 10000000
    return easting, northing


def vincenty_distancia(p1, p2):
    lon1, lat1 = map(math.radians, p1)
    lon2, lat2 = map(math.radians, p2)
    u1 = math.atan((1 - F) * math.tan(lat1))
    u2 = math.atan((1 - F) * math.tan(lat2))
    lmb = lon2 - lon1
    lam = lmb
    for _ in range(100):
        sin_lam = math.sin(lam)
        cos_lam = math.cos(lam)
        sin_sigma = math.sqrt((math.cos(u2) * sin_lam) ** 2 + (math.cos(u1) * math.sin(u2) - math.sin(u1) * math.cos(u2) * cos_lam) ** 2)
        if sin_sigma == 0:
            return 0.0
        cos_sigma = math.sin(u1) * math.sin(u2) + math.cos(u1) * math.cos(u2) * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = math.cos(u1) * math.cos(u2) * sin_lam / sin_sigma
        cos2_alpha = 1 - sin_alpha ** 2
        cos2_sigma_m = 0 if cos2_alpha == 0 else cos_sigma - 2 * math.sin(u1) * math.sin(u2) / cos2_alpha
        c = F / 16 * cos2_alpha * (4 + F * (4 - 3 * cos2_alpha))
        prev = lam
        lam = lmb + (1 - c) * F * sin_alpha * (
            sigma + c * sin_sigma * (cos2_sigma_m + c * cos_sigma * (-1 + 2 * cos2_sigma_m ** 2))
        )
        if abs(lam - prev) < 1e-12:
            break
    u2v = cos2_alpha * (A ** 2 - B ** 2) / (B ** 2)
    big_a = 1 + u2v / 16384 * (4096 + u2v * (-768 + u2v * (320 - 175 * u2v)))
    big_b = u2v / 1024 * (256 + u2v * (-128 + u2v * (74 - 47 * u2v)))
    delta_sigma = big_b * sin_sigma * (
        cos2_sigma_m + big_b / 4 * (
            cos_sigma * (-1 + 2 * cos2_sigma_m ** 2)
            - big_b / 6 * cos2_sigma_m * (-3 + 4 * sin_sigma ** 2) * (-3 + 4 * cos2_sigma_m ** 2)
        )
    )
    return B * big_a * (sigma - delta_sigma)


def azimute(p1, p2):
    lon1, lat1 = map(math.radians, p1)
    lon2, lat2 = map(math.radians, p2)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def grau_para_dms(valor):
    graus = int(valor)
    minutos_float = (valor - graus) * 60
    minutos = int(minutos_float)
    segundos = (minutos_float - minutos) * 60
    return f"{graus:03d}°{minutos:02d}'{segundos:05.2f}\""


def area_perimetro_utm(pontos_utm):
    area = 0.0
    perimetro = 0.0
    for i, ponto in enumerate(pontos_utm):
        prox = pontos_utm[(i + 1) % len(pontos_utm)]
        area += ponto[0] * prox[1] - prox[0] * ponto[1]
        perimetro += math.dist(ponto, prox)
    return abs(area) / 2, perimetro


def montar_dados(pontos):
    lon_c = sum(p[0] for p in pontos) / len(pontos)
    lat_c = sum(p[1] for p in pontos) / len(pontos)
    zone = utm_zone(lon_c)
    hemisferio = "S" if lat_c < 0 else "N"
    pontos_utm = [lonlat_para_utm(lon, lat, zone) for lon, lat in pontos]
    area, perimetro = area_perimetro_utm(pontos_utm)

    segmentos = []
    for i, ponto in enumerate(pontos):
        prox = pontos[(i + 1) % len(pontos)]
        easting, northing = pontos_utm[i]
        segmentos.append({
            "vertice": f"V{i + 1:02d}",
            "para": f"V{((i + 1) % len(pontos)) + 1:02d}",
            "azimute": grau_para_dms(azimute(ponto, prox)),
            "distancia": round(vincenty_distancia(ponto, prox), 2),
            "eLong": round(easting, 3),
            "nLat": round(northing, 3),
            "longitude": round(ponto[0], 8),
            "latitude": round(ponto[1], 8),
            "confrontante": ""
        })

    return {
        "processo": PROCESSO,
        "bairro": BAIRRO,
        "fusoUTM": f"{zone}{hemisferio}",
        "area_m2": round(area, 2),
        "perimetro_m": round(perimetro, 2),
        "dadosPerimetro": segmentos,
        "pontos_utm": pontos_utm
    }


def gerar_json(dados):
    path = OUT_DIR.joinpath("dados_perimetro_051201571_2026.json")
    serializavel = {k: v for k, v in dados.items() if k != "pontos_utm"}
    path.write_text(json.dumps(serializavel, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def gerar_memorial_pdf(dados):
    path = OUT_DIR.joinpath("memorial_051201571_2026.pdf")
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Memorial Descritivo Preliminar", styles["Title"]),
        Paragraph(f"REURB Coletivo: {PROCESSO}", styles["Normal"]),
        Paragraph(f"Núcleo/Bairro: {BAIRRO}", styles["Normal"]),
        Paragraph(f"Área: {dados['area_m2']:.2f} m²", styles["Normal"]),
        Paragraph(f"Perímetro: {dados['perimetro_m']:.2f} m", styles["Normal"]),
        Paragraph(f"Fuso UTM: {dados['fusoUTM']} - SIRGAS 2000", styles["Normal"]),
        Spacer(1, 0.5 * cm),
    ]
    table_data = [["Vértice", "Para", "Azimute", "Dist. (m)", "E", "N"]]
    for seg in dados["dadosPerimetro"]:
        table_data.append([
            seg["vertice"], seg["para"], seg["azimute"], f"{seg['distancia']:.2f}",
            f"{seg['eLong']:.3f}", f"{seg['nLat']:.3f}"
        ])
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Documento preliminar gerado a partir do shapefile local; a peça oficial deve ser validada no ArcGIS Pro.", styles["Italic"]))
    doc.build(story)
    return path


def gerar_planta_pdf(dados):
    path = OUT_DIR.joinpath("planta_preliminar_051201571_2026.pdf")
    c = canvas.Canvas(str(path), pagesize=landscape(A4))
    width, height = landscape(A4)
    margem = 2 * cm

    pontos = dados["pontos_utm"]
    min_x = min(p[0] for p in pontos)
    max_x = max(p[0] for p in pontos)
    min_y = min(p[1] for p in pontos)
    max_y = max(p[1] for p in pontos)
    escala = min((width - 2 * margem) / (max_x - min_x), (height - 4 * margem) / (max_y - min_y))

    def escala_ponto(p):
        x = margem + (p[0] - min_x) * escala
        y = margem + (p[1] - min_y) * escala
        return x, y

    c.setFont("Helvetica-Bold", 14)
    c.drawString(margem, height - margem, "Planta Preliminar do Núcleo")
    c.setFont("Helvetica", 9)
    c.drawString(margem, height - margem - 14, f"REURB Coletivo: {PROCESSO} | Bairro: {BAIRRO} | Área: {dados['area_m2']:.2f} m² | Perímetro: {dados['perimetro_m']:.2f} m | Fuso: {dados['fusoUTM']}")

    path_points = [escala_ponto(p) for p in pontos]
    c.setStrokeColor(colors.darkgreen)
    c.setFillColor(colors.Color(0.72, 0.88, 0.68, alpha=0.35))
    c.setLineWidth(1.5)
    p = c.beginPath()
    p.moveTo(*path_points[0])
    for xy in path_points[1:]:
        p.lineTo(*xy)
    p.close()
    c.drawPath(p, stroke=1, fill=1)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 7)
    for i, xy in enumerate(path_points):
        c.circle(xy[0], xy[1], 2, stroke=1, fill=1)
        c.drawString(xy[0] + 3, xy[1] + 3, f"V{i + 1:02d}")

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margem, 1.1 * cm, "Planta preliminar gerada fora do layout oficial do ArcGIS Pro.")
    c.save()
    return path


def gerar_zip_shp():
    path = OUT_DIR.joinpath("bairro_camada_051201571_2026.zip")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arquivo in SHP.parent.glob("bairro_camada.*"):
            if ".lock" not in arquivo.name.lower():
                zf.write(arquivo, arquivo.name)
    return path


def main():
    OUT_DIR.mkdir(exist_ok=True)
    rows = ler_dbf(SHP.with_suffix(".dbf"))
    row = rows[0] if rows else {}
    pontos = ler_poligono(SHP)
    dados = montar_dados(pontos)
    dados["registro"] = row

    arquivos = [
        gerar_json(dados),
        gerar_memorial_pdf(dados),
        gerar_planta_pdf(dados),
        gerar_zip_shp(),
    ]

    for arquivo in arquivos:
        print(arquivo)


if __name__ == "__main__":
    main()
