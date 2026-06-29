# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path


STATUS_LEGENDA = {
    0: "Sem status",
    1: "Beneficiário",
    2: "Vago",
    3: "Em análise",
    4: "Beneficiário validado",
    5: "Uso institucional",
    6: "Área pública",
    7: "Área rural",
    8: "Área verde",
    9: "Sistema viário",
    10: "Conflito/pendência",
    11: "Outro",
}


def _decimal_texto(valor, casas=4):
    if valor is None or valor == "":
        return ""
    return f"{float(valor):.{casas}f}".replace(".", ",")


def _paragrafo(valor, estilo):
    from reportlab.platypus import Paragraph

    texto = "" if valor is None else str(valor)
    texto = (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return Paragraph(texto, estilo)


def gerar(payload_path, saida_pdf=None):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    payload_path = Path(payload_path)
    with payload_path.open("r", encoding="utf-8") as arquivo:
        payload = json.load(arquivo)

    saida = Path(saida_pdf or payload["saida_pdf"])
    saida.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloAreasTrabalhadas",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceAfter=6,
    )
    subtitulo = ParagraphStyle(
        "SubtituloAreasTrabalhadas",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=8.5,
        leading=11,
        spaceAfter=10,
    )
    normal = ParagraphStyle(
        "NormalAreasTrabalhadas",
        parent=styles["Normal"],
        fontSize=7,
        leading=8,
    )
    cabecalho = ParagraphStyle(
        "CabecalhoAreasTrabalhadas",
        parent=normal,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    nota = ParagraphStyle(
        "NotaAreasTrabalhadas",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#333333"),
    )

    doc = SimpleDocTemplate(
        str(saida),
        pagesize=landscape(A4),
        rightMargin=1.1 * cm,
        leftMargin=1.1 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )

    story = [
        Paragraph("QUADRO DE ÁREAS TRABALHADAS", titulo),
        Paragraph(
            "Processo REURB Coletivo: {numero} | Bairro: {bairro} | Município: {municipio}".format(
                numero=payload.get("numero_reurb_coletivo", ""),
                bairro=payload.get("bairro", ""),
                municipio=payload.get("municipio", ""),
            ),
            subtitulo,
        ),
    ]

    resumo = payload.get("resumo_status", [])
    total_lotes = sum(item.get("quantidade", 0) for item in resumo)
    total_area = sum(float(item.get("area_m2") or 0) for item in resumo)

    resumo_data = [[
        _paragrafo("Status", cabecalho),
        _paragrafo("Qtd.", cabecalho),
        _paragrafo("Área (m²)", cabecalho),
        _paragrafo("% da área", cabecalho),
    ]]
    for item in resumo:
        area = float(item.get("area_m2") or 0)
        percentual = (area / total_area * 100) if total_area else 0
        resumo_data.append([
            _paragrafo(item.get("status_nome", ""), normal),
            _paragrafo(item.get("quantidade", ""), normal),
            _paragrafo(_decimal_texto(area), normal),
            _paragrafo(_decimal_texto(percentual, 2), normal),
        ])
    resumo_data.append([
        _paragrafo("TOTAL", cabecalho),
        _paragrafo(total_lotes, cabecalho),
        _paragrafo(_decimal_texto(total_area), cabecalho),
        _paragrafo("100,00", cabecalho),
    ])

    tabela_resumo = Table(resumo_data, colWidths=[7.6 * cm, 2.0 * cm, 3.2 * cm, 2.4 * cm], repeatRows=1)
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EDEDED")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tabela_resumo)
    story.append(Spacer(1, 0.3 * cm))

    linhas = [[
        _paragrafo("Quadra", cabecalho),
        _paragrafo("Lote", cabecalho),
        _paragrafo("Beneficiário/ocupante", cabecalho),
        _paragrafo("CPF/CNPJ", cabecalho),
        _paragrafo("Status", cabecalho),
        _paragrafo("Área (m²)", cabecalho),
    ]]
    for item in payload.get("lotes", []):
        status = item.get("status")
        status_nome = item.get("status_nome") or STATUS_LEGENDA.get(status, str(status or ""))
        linhas.append([
            _paragrafo(item.get("quadra", ""), normal),
            _paragrafo(item.get("lote", ""), normal),
            _paragrafo(item.get("nome", ""), normal),
            _paragrafo(item.get("cpf_cnpj", ""), normal),
            _paragrafo(status_nome, normal),
            _paragrafo(_decimal_texto(item.get("area_m2")), normal),
        ])

    tabela = Table(
        linhas,
        colWidths=[2.0 * cm, 2.0 * cm, 8.0 * cm, 4.0 * cm, 5.0 * cm, 3.0 * cm],
        repeatRows=1,
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (1, -1), "CENTER"),
        ("ALIGN", (5, 1), (5, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Nota técnica: as áreas foram calculadas a partir da camada de lotes reprojetada para o fuso UTM "
        "identificado no processamento. Este anexo consolida as áreas trabalhadas por lote e por status cadastral.",
        nota,
    ))

    doc.build(story)
    return saida


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python gerar_quadro_areas_trabalhadas.py payload.json [saida.pdf]")
    saida_arg = sys.argv[2] if len(sys.argv) > 2 else None
    print(gerar(sys.argv[1], saida_arg))
