# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BRASAO_PATH = Path(r"C:\Users\gusta\Downloads\Brasão_do_Maranhão.png")
LOGO_GOVERNO_PATH = Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_Maranhão_(2023-2027).png")


def decimal_texto(valor, casas=4):
    if valor is None or valor == "":
        return ""
    return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar_azimute(valor):
    return str(valor or "").replace("′", "'").replace("″", '"')


def montar_descricao(dados_perimetro):
    if not dados_perimetro:
        return ""

    partes = []
    primeiro = dados_perimetro[0]
    partes.append(
        "Inicia-se a descrição no vértice "
        f"<b>{primeiro.get('vertice', '')}</b>, na coordenada "
        f"E= {decimal_texto(primeiro.get('eLong'))} e N= {decimal_texto(primeiro.get('nLat'))}"
    )

    for indice, item in enumerate(dados_perimetro):
        proximo = dados_perimetro[(indice + 1) % len(dados_perimetro)]
        trecho_inicial = "deste segue" if indice else "segue"
        confrontante = item.get("confrontante") or "confrontante não informado"
        partes.append(
            f"{trecho_inicial} com azimute de {normalizar_azimute(item.get('azimute'))} "
            f"e distância de {decimal_texto(item.get('distancia'))} m até o vértice "
            f"<b>{proximo.get('vertice', '')}</b>, de coordenada "
            f"E= {decimal_texto(proximo.get('eLong'))} e N= {decimal_texto(proximo.get('nLat'))}, "
            f"confrontando com {confrontante}"
        )

    partes.append("fechando assim o perímetro descrito.")
    return ", ".join(partes)


def montar_paragrafo_referencias(perimetro):
    fuso = perimetro.get("fusoUTM", "")
    meridiano = perimetro.get("meridianoCentral", "")
    try:
        meridiano_texto = f"{abs(float(meridiano)):.0f}°"
    except Exception:
        meridiano_texto = "45°"

    return (
        "Todas as coordenadas aqui descritas estão plotadas na Carta Planimétrica Cadastral anexa, "
        "bem como georreferenciadas ao Sistema Geodésico Brasileiro (SGB), e encontram-se "
        f"representadas na Projeção Universal Transversa de Mercator (UTM), Fuso {fuso}, "
        f"referenciadas ao Meridiano Central de {meridiano_texto}, tendo como datum horizontal "
        "o SIRGAS 2000 (elipsoide GRS-80/Sistema de Referência Geocêntrico para as Américas). "
        "A área foi obtida pelas coordenadas plano-retangulares referenciadas ao Sistema "
        "Geodésico Brasileiro (SGB). Todos os azimutes foram calculados no plano da projeção UTM. "
        "O perímetro e as distâncias foram calculados pelas coordenadas plano-retangulares. "
        "A execução do levantamento in situ atende aos parâmetros estabelecidos pelas Especificações "
        "e Normas para Levantamentos Geodésicos Associados ao Sistema Geodésico Brasileiro "
        "(IBGE, 2017), pelas normas da Associação Brasileira de Normas Técnicas (ABNT), "
        "especialmente a ABNT NBR 13.133 (2ª ed., 2021), Execução de Levantamento Topográfico, "
        "a ABNT NBR 17.047 (1ª ed., 2022), Levantamento Cadastral Territorial para Registro "
        "Público, e a Norma Técnica para Georreferenciamento de Imóveis Rurais (3ª ed., 2013), "
        "do Instituto Nacional de Colonização e Reforma Agrária (INCRA)."
    )


def logo(path, width, height):
    if path.exists():
        return Image(str(path), width=width, height=height, kind="proportional")
    return ""


def gerar(json_path, out_path=None):
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    identificacao = data["identificacaoPlanilha"]
    perimetro = identificacao["perimetros"][0]
    dados = perimetro.get("dadosPerimetro", [])

    numero = identificacao.get("numeroProcessoColetivo", "")
    bairro = identificacao.get("bairro", "")
    municipio = perimetro.get("municipio") or (identificacao.get("municipios") or [""])[0]
    area = identificacao.get("areaTotal") or perimetro.get("areaPerimetro")
    perimetro_total = identificacao.get("perimetroTotal")
    responsavel = identificacao.get("responsavelTecnico", {})

    if out_path is None:
        out_path = json_path.with_name(f"memorial_descritivo_{numero.replace('/', '_')}.pdf")
    out_path = Path(out_path)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.25 * cm,
        bottomMargin=1.35 * cm,
        title=f"Memorial Descritivo - {numero}",
    )

    styles = getSampleStyleSheet()
    orgao = ParagraphStyle(
        "Orgao",
        parent=styles["Normal"],
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
    )
    orgao_sub = ParagraphStyle(
        "OrgaoSub",
        parent=styles["Normal"],
        alignment=TA_LEFT,
        fontName="Helvetica",
        fontSize=8.1,
        leading=9.3,
        textColor=colors.HexColor("#333333"),
    )
    title = ParagraphStyle(
        "TitleMemorial",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        spaceAfter=8,
        textColor=colors.HexColor("#111111"),
    )
    section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        fontSize=10.8,
        leading=14,
        textColor=colors.HexColor("#111111"),
        spaceBefore=8,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "BodyJustify",
        parent=styles["Normal"],
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
        fontSize=9.15,
        leading=13.5,
        firstLineIndent=18,
    )
    small_center = ParagraphStyle(
        "SmallCenter",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontName="Helvetica",
        fontSize=8.8,
        leading=11,
    )

    header_text = [
        Paragraph("GOVERNO DO ESTADO DO MARANHÃO", orgao),
        Paragraph("INSTITUTO DE COLONIZAÇÃO E TERRAS DO MARANHÃO - ITERMA", orgao_sub),
    ]
    header = Table(
        [[
            logo(BRASAO_PATH, 1.38 * cm, 1.38 * cm),
            header_text,
            logo(LOGO_GOVERNO_PATH, 3.55 * cm, 1.18 * cm),
            Paragraph("ITERMA", ParagraphStyle("Iterma", parent=orgao, alignment=TA_CENTER, fontSize=11.5, leading=12)),
        ]],
        colWidths=[1.55 * cm, 9.45 * cm, 3.65 * cm, 2.05 * cm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.8, colors.black),
        ("LINEBEFORE", (3, 0), (3, 0), 0.6, colors.black),
    ]))

    story = [
        header,
        Spacer(1, 0.35 * cm),
        Paragraph("MEMORIAL DESCRITIVO", title),
    ]

    tabela_info = Table(
        [
            [
                Paragraph(f"<b>Bairro:</b> {bairro}", styles["Normal"]),
                Paragraph(f"<b>Município/UF:</b> {municipio} - MA", styles["Normal"]),
            ],
            [
                Paragraph(f"<b>Área:</b> {decimal_texto(area, 2)} m²", styles["Normal"]),
                Paragraph(f"<b>Perímetro:</b> {decimal_texto(perimetro_total, 2)} m", styles["Normal"]),
            ],
            [
                Paragraph(f"<b>Processo REURB Coletivo:</b> {numero}", styles["Normal"]),
                Paragraph(f"<b>Fuso UTM:</b> {perimetro.get('fusoUTM', '')}", styles["Normal"]),
            ],
        ],
        colWidths=[8.3 * cm, 8.3 * cm],
    )
    tabela_info.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#333333")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7F7F7")),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    nota_tecnica = Table(
        [[Paragraph(
            "<b>Nota técnica:</b> este memorial apresenta a descrição analítica completa do perímetro, "
            "com a sequência integral de vértices e coordenadas.",
            styles["Normal"]
        )]],
        colWidths=[16.6 * cm],
    )
    nota_tecnica.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#555555")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7D6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.extend([
        tabela_info,
        Spacer(1, 0.35 * cm),
        nota_tecnica,
        Spacer(1, 0.35 * cm),
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#333333")),
        Paragraph("DESCRIÇÃO DO PERÍMETRO", section),
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#333333")),
        Spacer(1, 0.25 * cm),
        Paragraph(montar_descricao(dados), body),
        Spacer(1, 0.25 * cm),
        Paragraph(montar_paragrafo_referencias(perimetro), body),
        Spacer(1, 0.25 * cm),
    ])

    nome = responsavel.get("nome", "")
    formacao = responsavel.get("formacao", "")
    registro = responsavel.get("codigoCredenciamento", "")
    assinatura = Table(
        [
            [""],
            ["____________________________________________"],
            [nome],
            [" - ".join([valor for valor in [formacao, registro] if valor])],
            ["Responsável Técnico"],
        ],
        colWidths=[10 * cm],
        splitByRow=0,
    )
    assinatura.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("TOPPADDING", (0, 0), (0, 0), 6),
    ]))
    story.append(KeepTogether([
        assinatura,
    ]))

    doc.build(story)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Uso: python gerar_memorial_descritivo.py resultado.json [saida.pdf]")
    saida = gerar(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
    print(saida)
