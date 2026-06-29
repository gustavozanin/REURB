# -*- coding: utf-8 -*-

import json
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


BRASAO_CANDIDATOS = [
    Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_Maranhão_(2023-2027).png"),
    Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_MaranhÃ£o_(2023-2027).png"),
]


def _logo_existente():
    for caminho in BRASAO_CANDIDATOS:
        if caminho.exists():
            return str(caminho)
    return None


def _fmt(valor, casas=2):
    return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ponto(nome, este, norte):
    return f"{nome} de coordenada E= {_fmt(este, 4)} e N= {_fmt(norte, 4)}"


def _descricao_segmentos(segmentos):
    partes = []
    if not segmentos:
        return ""
    primeiro = segmentos[0]
    partes.append(
        "Inicia-se a descricao no vertice "
        + _ponto(primeiro["de"], primeiro["este_de"], primeiro["norte_de"])
        + ", "
    )
    for idx, segmento in enumerate(segmentos):
        prefixo = "" if idx == 0 else "deste segue "
        partes.append(
            f"{prefixo}com azimute de {segmento['azimute']} e distancia de {_fmt(segmento['distancia'], 2)}m "
            f"ate o vertice {_ponto(segmento['para'], segmento['este_para'], segmento['norte_para'])}, "
            f"confrontando com {segmento.get('confrontante') or 'area adjacente'}, "
        )
    if partes:
        partes[-1] = partes[-1].rstrip(", ") + "."
    return "".join(partes)


def gerar_memorial_pdf(dados_json, saida_pdf):
    dados = json.loads(Path(dados_json).read_text(encoding="utf-8"))
    saida_pdf = Path(saida_pdf)
    saida_pdf.parent.mkdir(parents=True, exist_ok=True)

    styles = {
        "cabecalho": ParagraphStyle("cabecalho", fontName="Helvetica", fontSize=10, leading=12, alignment=TA_CENTER),
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=12, leading=15, alignment=TA_CENTER),
        "normal": ParagraphStyle("normal", fontName="Helvetica", fontSize=10.5, leading=13.2, alignment=TA_LEFT),
        "justificado": ParagraphStyle("justificado", fontName="Helvetica", fontSize=10.5, leading=13.2, alignment=TA_JUSTIFY),
        "assinatura": ParagraphStyle("assinatura", fontName="Helvetica", fontSize=10, leading=12, alignment=TA_CENTER),
    }

    story = []
    logo = _logo_existente()
    if logo:
        story.append(Image(logo, width=5.0 * cm, height=1.0 * cm, kind="proportional"))
    story.extend([
        Paragraph("ESTADO DO MARANHAO", styles["cabecalho"]),
        Paragraph("SECRETARIA DE ESTADO DA AGRICULTURA FAMILIAR - SAF", styles["cabecalho"]),
        Paragraph("INSTITUTO DE COLONIZACAO E TERRAS DO MARANHAO - ITERMA", styles["cabecalho"]),
        Spacer(1, 0.6 * cm),
        Paragraph("MEMORIAL DESCRITIVO", styles["titulo"]),
        Spacer(1, 0.45 * cm),
        Paragraph(f"Municipio/UF: {dados['municipio']} - MA", styles["normal"]),
        Paragraph(f"Nucleos/Bairros: {', '.join(dados.get('bairros', []))}", styles["normal"]),
        Spacer(1, 0.25 * cm),
        Paragraph(f"Area: {_fmt(dados['area_total'], 2)} m2", styles["normal"]),
        Paragraph(f"Perimetro: {_fmt(dados['perimetro_total'], 2)} m", styles["normal"]),
        Spacer(1, 0.65 * cm),
        Paragraph("_" * 100, styles["cabecalho"]),
        Paragraph("DESCRICAO DO PERIMETRO", styles["titulo"]),
        Paragraph("_" * 100, styles["cabecalho"]),
        Spacer(1, 0.25 * cm),
        Paragraph(_descricao_segmentos(dados.get("segmentos", [])), styles["justificado"]),
        Spacer(1, 0.35 * cm),
        Paragraph(
            "Todas as coordenadas aqui descritas estao georreferenciadas ao Sistema Geodesico Brasileiro (SGB) "
            "e encontram-se representadas no Sistema UTM, referenciadas ao SIRGAS 2000, Fuso 23S. "
            "A area, o perimetro, os azimutes e as distancias foram calculados no plano de projecao UTM.",
            styles["justificado"],
        ),
        Spacer(1, 0.65 * cm),
        Paragraph(dados.get("local_data", ""), styles["cabecalho"]),
        Spacer(1, 1.0 * cm),
        Paragraph("________________________________________", styles["assinatura"]),
        Paragraph("Responsavel Tecnico", styles["assinatura"]),
        Paragraph(dados.get("responsavel", {}).get("nome", ""), styles["assinatura"]),
        Paragraph(dados.get("responsavel", {}).get("formacao", ""), styles["assinatura"]),
        Paragraph(dados.get("responsavel", {}).get("registro", ""), styles["assinatura"]),
    ])

    doc = SimpleDocTemplate(
        str(saida_pdf),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.6 * cm,
    )
    doc.build(story)
    return str(saida_pdf)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gera memorial geral em PDF.")
    parser.add_argument("--dados", required=True)
    parser.add_argument("--saida", required=True)
    args = parser.parse_args()
    print(gerar_memorial_pdf(args.dados, args.saida))
