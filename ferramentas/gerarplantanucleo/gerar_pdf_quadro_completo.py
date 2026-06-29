# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


LINHAS_POR_BLOCO = 30
COLUNAS_POR_PAGINA = 2


def decimal_texto(valor):
    if valor is None or valor == "":
        return ""
    return f"{float(valor):.4f}".replace(".", ",")


def titulo_quadro(identificacao):
    numero = identificacao.get("numeroProcessoColetivo", "")
    bairro = identificacao.get("bairro", "")
    objetivo = identificacao.get("objetivo", "Regularização Fundiária Urbana - REURB")
    municipio = ""
    perimetros = identificacao.get("perimetros") or []
    if perimetros:
        municipio = perimetros[0].get("municipio", "")

    partes = [
        "Quadro de Coordenadas da Planta Simplificada",
        f"Processo REURB Coletivo: {numero}",
    ]
    if bairro:
        partes.append(f"Bairro: {bairro}")
    if municipio:
        partes.append(f"Município: {municipio}")
    if objetivo:
        partes.append(f"Objetivo: {objetivo}")
    return " | ".join(partes)


def gerar(json_path):
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    identificacao = data["identificacaoPlanilha"]
    numero = identificacao["numeroProcessoColetivo"]
    dados = identificacao["perimetros"][0]["dadosPerimetro"]
    responsavel = identificacao.get("responsavelTecnico", {})
    nome_resp = responsavel.get("nome") or "Responsavel tecnico"
    detalhe_resp = " - ".join(
        valor for valor in [
            responsavel.get("formacao", ""),
            responsavel.get("codigoCredenciamento", "")
        ]
        if valor
    )

    out_path = json_path.with_name(f"quadro_coordenadas_{numero.replace('/', '_')}.pdf")
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=landscape(A4),
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        "TituloQuadro",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.8,
        leading=10.5,
        spaceAfter=4,
    )
    nota_style = ParagraphStyle(
        "NotaRodape",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor("#333333"),
    )
    story = [
        Paragraph(titulo_quadro(identificacao), titulo_style),
        Spacer(1, 0.08 * cm)
    ]

    linhas = []
    for item in dados:
        linhas.append([
            item.get("vertice", ""),
            item.get("confrontante", "") or "",
            item.get("azimute", ""),
            decimal_texto(item.get("distancia", "")),
            decimal_texto(item.get("eLong", "")),
            decimal_texto(item.get("nLat", "")),
        ])

    estilo_tabela = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 5.0),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])

    cabecalho = ["De", "Conf.", "Azimute", "D(m)", "E", "N"]
    larguras_colunas = [1.0 * cm, 3.7 * cm, 2.4 * cm, 1.6 * cm, 2.3 * cm, 2.3 * cm]
    blocos = [linhas[i:i + LINHAS_POR_BLOCO] for i in range(0, len(linhas), LINHAS_POR_BLOCO)]

    for indice in range(0, len(blocos), COLUNAS_POR_PAGINA):
        tabelas_lado_a_lado = []
        for bloco in blocos[indice:indice + COLUNAS_POR_PAGINA]:
            tabela = Table([cabecalho] + bloco, repeatRows=1, colWidths=larguras_colunas)
            tabela.setStyle(estilo_tabela)
            tabelas_lado_a_lado.append(tabela)

        while len(tabelas_lado_a_lado) < COLUNAS_POR_PAGINA:
            tabelas_lado_a_lado.append("")

        pagina = Table([tabelas_lado_a_lado], colWidths=[13.75 * cm, 13.75 * cm])
        pagina.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(pagina)
        story.append(Spacer(1, 0.18 * cm))

    story.append(Spacer(1, 0.15 * cm))
    assinatura = Table([
        [""],
        ["____________________________________________"],
        [nome_resp],
        [detalhe_resp],
    ], colWidths=[10 * cm])
    assinatura.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
        ("TOPPADDING", (0, 0), (0, 0), 8),
    ]))
    story.append(assinatura)
    story.append(Spacer(1, 0.08 * cm))
    story.append(Paragraph(
        "ATENÇÃO: Este anexo corresponde aos vértices simplificados exibidos na planta principal. A sequência analítica completa do perímetro encontra-se no Memorial Descritivo.",
        nota_style
    ))
    doc.build(story)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python gerar_pdf_quadro_completo.py caminho_do_resultado.json")
    print(gerar(sys.argv[1]))
