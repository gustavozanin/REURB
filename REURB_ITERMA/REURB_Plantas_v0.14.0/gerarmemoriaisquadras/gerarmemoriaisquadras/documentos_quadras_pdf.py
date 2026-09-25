# -*- coding: utf-8 -*-
"""Geração e consolidação dos memoriais A4."""
import html
import sys
from pathlib import Path

# O ArcGIS Pro ignora pacotes instalados na pasta do usuário (o pip usa esse
# destino quando não tem permissão em Program Files), por isso reportlab e
# pypdf ficam aqui dentro da ferramenta.
# Vai no fim do sys.path para não sobrepor nada que já exista no ambiente
# do Pro.
_LIBS = Path(__file__).resolve().parent / "libs"
if _LIBS.is_dir() and str(_LIBS) not in sys.path:
    sys.path.append(str(_LIBS))


def _br(v, casas=2):
    return (
        f"{float(v or 0):,.{casas}f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def gerar_pdf(segmentos, meta, caminho):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Image,
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise ImportError(
            "reportlab não encontrado. Refaça a pasta de bibliotecas da "
            "ferramenta com o Python do ArcGIS Pro:\n"
            f'propy.bat -m pip install --target "{_LIBS}" --no-deps '
            "reportlab pypdf"
        ) from exc
    base = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "titulo", parent=base["Title"], alignment=TA_CENTER, fontSize=14
    )
    corpo = ParagraphStyle(
        "corpo",
        parent=base["BodyText"],
        alignment=TA_JUSTIFY,
        fontSize=9.5,
        leading=13,
    )
    centro = ParagraphStyle(
        "centro", parent=base["BodyText"], alignment=TA_CENTER, fontSize=9
    )
    story = []
    logo = (
        Path(__file__).resolve().parents[2]
        / "gerarplantaverticesconfrontantesmemorial"
        / "gerarplantaverticesconfrontantesmemorial"
        / "layout"
        / "assets"
        / "logo_governo_maranhao.png"
    )
    if logo.exists():
        story.append(
            Image(str(logo), width=4 * cm, height=1.2 * cm, kind="proportional")
        )
    story += [
        Paragraph("GOVERNO DO ESTADO DO MARANHÃO", centro),
        Paragraph(
            "INSTITUTO DE COLONIZAÇÃO E TERRAS DO MARANHÃO — ITERMA", centro
        ),
        Spacer(1, 0.4 * cm),
        Paragraph("MEMORIAL DESCRITIVO DA QUADRA", titulo),
    ]
    info = Table(
        [
            [f"Quadra: {meta['quadra']}", f"Bairro: {meta['bairro']}"],
            [
                f"Processo: {meta['numero_reurb']}",
                f"SIRGAS 2000 / UTM: EPSG {meta['wkid']}",
            ],
            [
                f"Área: {_br(meta['area_m2'])} m²",
                f"Perímetro: {_br(meta['perimetro_m'])} m",
            ],
        ],
        colWidths=[8.2 * cm, 8.2 * cm],
    )
    info.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    partes = []
    if segmentos:
        p = segmentos[0]
        partes.append(
            f"Inicia-se a descrição no vértice "
            f"<b>{html.escape(p['vertice'])}</b>, de coordenadas "
            f"E={_br(p['eLong'], 4)} e N={_br(p['nLat'], 4)}"
        )
        for x in segmentos:
            partes.append(
                f"do vértice <b>{html.escape(x['vertice'])}</b>, "
                f"confrontando com {html.escape(x['confrontante'])}, "
                f"segue com azimute {html.escape(x['azimute'])} e "
                f"distância {_br(x['distancia'])} m até o vértice "
                f"<b>{html.escape(x['vertice_para'])}</b>, de coordenadas "
                f"E={_br(x['este_para'], 4)} e N={_br(x['norte_para'], 4)}"
            )
        partes.append("fechando assim o perímetro descrito.")
    credencial = " — ".join(
        x for x in [meta.get("rt_formacao"), meta.get("rt_crea")] if x
    )
    # Nota técnica e assinatura ficam juntas: se não couber no fim da
    # descrição, o bloco inteiro vai para a página seguinte (sem vazio
    # entre o texto SIRGAS e o nome do responsável técnico).
    assinatura = Table(
        [
            [
                Paragraph(
                    "Coordenadas referenciadas ao SIRGAS 2000, projeção UTM "
                    f"({html.escape(meta['sistema_referencia'])}). Área, "
                    "perímetro, azimutes e distâncias foram calculados no "
                    "plano da projeção.",
                    corpo,
                )
            ],
            ["________________________________________"],
            [html.escape(meta.get("rt_nome") or "Responsável Técnico")],
            [html.escape(credencial)],
        ],
        colWidths=[16.4 * cm],
        splitByRow=0,
    )
    assinatura.setStyle(TableStyle([
        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 1), (0, 1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story += [
        Spacer(1, 0.3 * cm),
        info,
        Spacer(1, 0.5 * cm),
        Paragraph("DESCRIÇÃO DO PERÍMETRO", titulo),
        Paragraph(", ".join(partes), corpo),
        Spacer(1, 0.35 * cm),
        KeepTogether([assinatura]),
    ]
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(
        str(caminho),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.4 * cm,
    ).build(story)
    return caminho


def mesclar_pdfs(pdfs, caminho):
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise ImportError(
            "pypdf não encontrado. Refaça a pasta de bibliotecas da "
            "ferramenta:\n"
            f'propy.bat -m pip install --target "{_LIBS}" --no-deps '
            "reportlab pypdf"
        ) from exc
    writer = PdfWriter()
    for pdf in pdfs:
        for pagina in PdfReader(pdf).pages:
            writer.add_page(pagina)
    with open(caminho, "wb") as arquivo:
        writer.write(arquivo)
    return caminho
