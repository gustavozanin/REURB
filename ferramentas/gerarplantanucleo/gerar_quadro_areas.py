# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


def _decimal_texto(valor, casas=4):
    if valor is None or valor == "":
        return ""
    return f"{float(valor):.{casas}f}".replace(".", ",")


def gerar(
    numero_reurb_coletivo,
    bairro,
    municipio,
    area_bairro,
    perimetro_bairro,
    fusoutm,
    banda,
    meridiano_central,
    responsavel_tecnico,
    funcao,
    n_crea_cau,
    data,
    saida_pdf,
):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    saida_pdf = Path(saida_pdf)
    saida_pdf.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloQuadroAreas",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceAfter=8,
    )
    subtitulo = ParagraphStyle(
        "SubtituloQuadroAreas",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        leading=12,
        spaceAfter=12,
    )
    normal = ParagraphStyle(
        "NormalQuadroAreas",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )
    nota = ParagraphStyle(
        "NotaQuadroAreas",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#333333"),
    )

    doc = SimpleDocTemplate(
        str(saida_pdf),
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
    )

    story = [
        Paragraph("QUADRO DE ÁREAS", titulo),
        Paragraph(
            f"REURB Coletivo: {numero_reurb_coletivo} | Bairro: {bairro} | Município: {municipio}",
            subtitulo,
        ),
    ]

    dados = [
        ["Descrição", "Valor"],
        ["Área total do perímetro", f"{_decimal_texto(area_bairro)} m²"],
        ["Perímetro total", f"{_decimal_texto(perimetro_bairro)} m"],
        ["Sistema de referência", "SIRGAS 2000 / UTM"],
        ["Fuso UTM", str(fusoutm or "")],
        ["Banda UTM", str(banda or "")],
        ["Meridiano central", f"{_decimal_texto(meridiano_central)}"],
        ["Data de geração", str(data or "")],
    ]

    tabela = Table(dados, colWidths=[8.5 * cm, 7.0 * cm], repeatRows=1)
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 1), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#666666")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tabela)
    story.append(Spacer(1, 0.45 * cm))

    responsavel = [
        ["Responsável técnico", responsavel_tecnico or ""],
        ["Formação", funcao or ""],
        ["Registro", n_crea_cau or ""],
    ]
    tabela_resp = Table(responsavel, colWidths=[5.0 * cm, 10.5 * cm])
    tabela_resp.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#777777")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F0F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(tabela_resp)
    story.append(Spacer(1, 0.35 * cm))
    story.append(
        Paragraph(
            "Nota técnica: os valores deste quadro são calculados a partir do perímetro do bairro "
            "selecionado e reprojetado para o fuso UTM identificado no processamento da planta.",
            nota,
        )
    )
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("______________________________________________", normal))
    story.append(Paragraph(responsavel_tecnico or "", normal))
    story.append(Paragraph(f"{funcao or ''} - {n_crea_cau or ''}", normal))

    doc.build(story)
    return saida_pdf


def gerar_por_payload(payload_path, saida_pdf=None):
    payload_path = Path(payload_path)
    with payload_path.open("r", encoding="utf-8") as arquivo:
        payload = json.load(arquivo)

    saida = saida_pdf or payload.get("saida_pdf")
    return gerar(saida_pdf=saida, **{k: v for k, v in payload.items() if k != "saida_pdf"})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python gerar_quadro_areas.py payload.json [saida.pdf]")
    saida = sys.argv[2] if len(sys.argv) > 2 else None
    print(gerar_por_payload(sys.argv[1], saida))
