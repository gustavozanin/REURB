# -*- coding: utf-8 -*-

import argparse
import html
import json
import math
import os
import subprocess
import sys
import unicodedata
import datetime as dt
from pathlib import Path


PASTA_FERRAMENTA = Path(__file__).parent
PASTA_MOTOR = Path(r"C:\REURB\ferramentas\gerarpranchaloteamento")


def preparar_imports():
    for pasta in [str(PASTA_MOTOR), str(PASTA_FERRAMENTA)]:
        if pasta not in sys.path:
            sys.path.insert(0, pasta)


def slug_resultado(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    import re

    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "valor"


def decimal_texto(valor, casas=2):
    return f"{float(valor or 0):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _campo_existente(arcpy, dataset, candidatos):
    campos = {field.name.lower(): field.name for field in arcpy.ListFields(dataset)}
    for candidato in candidatos:
        if candidato.lower() in campos:
            return campos[candidato.lower()]
    return None


def _angulo_azimute(dx, dy):
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _azimute_texto(angulo):
    total = int(round(float(angulo) * 3600))
    graus = (total // 3600) % 360
    minutos = (total % 3600) // 60
    segundos = total % 60
    if graus == 360:
        graus = 0
    return f"{graus:03d}°{minutos:02d}'{segundos:02d}\""


def _segmentos_linha(arcpy, geom, prefixo="E"):
    sr_utm = arcpy.SpatialReference(31983)
    try:
        geom = geom.projectAs(sr_utm)
    except Exception:
        pass

    segmentos = []
    indice_ponto = 1
    for parte in geom:
        pontos = [p for p in parte if p]
        if len(pontos) < 2:
            continue
        nomes = [f"{prefixo}-P{indice_ponto + i:02d}" for i in range(len(pontos))]
        for i in range(len(pontos) - 1):
            ponto_de = pontos[i]
            ponto_para = pontos[i + 1]
            dx = ponto_para.X - ponto_de.X
            dy = ponto_para.Y - ponto_de.Y
            distancia = math.hypot(dx, dy)
            if distancia < 0.01:
                continue
            segmentos.append(
                {
                    "de": nomes[i],
                    "para": nomes[i + 1],
                    "azimute": _azimute_texto(_angulo_azimute(dx, dy)),
                    "distancia": distancia,
                    "este_de": ponto_de.X,
                    "norte_de": ponto_de.Y,
                    "este_para": ponto_para.X,
                    "norte_para": ponto_para.Y,
                }
            )
        indice_ponto += len(pontos)
    return segmentos


def _descricao_segmentos(dados):
    segmentos = dados.get("segmentos") or []
    if not segmentos:
        return ""
    primeiro = segmentos[0]
    logradouro = dados.get("logradouro") or "eixo viario"
    partes = [
        "Inicia-se a descricao linear do eixo viario "
        f"{logradouro} no vertice {primeiro['de']}, de coordenadas "
        f"E= {decimal_texto(primeiro['este_de'], 4)} e N= {decimal_texto(primeiro['norte_de'], 4)}, "
    ]
    for idx, segmento in enumerate(segmentos):
        prefixo = "" if idx == 0 else "deste segue "
        partes.append(
            f"{prefixo}com azimute de {segmento['azimute']} e distancia de "
            f"{decimal_texto(segmento['distancia'], 2)}m ate o vertice {segmento['para']}, "
            f"de coordenadas E= {decimal_texto(segmento['este_para'], 4)} "
            f"e N= {decimal_texto(segmento['norte_para'], 4)}, "
        )
    partes[-1] = partes[-1].rstrip(", ") + "."
    return "".join(partes)


def _dados_eixos(arcpy, shp_eixo, municipio, bairro, numero, responsavel):
    campo_logradouro = _campo_existente(arcpy, shp_eixo, ["logradouro", "nome", "rua"])
    sr_utm = arcpy.SpatialReference(31983)
    campos = [campo for campo in [campo_logradouro] if campo] + ["OID@", "SHAPE@"]
    dados = []
    usados = {}
    with arcpy.da.SearchCursor(shp_eixo, campos) as cursor:
        for row in cursor:
            idx = 0
            logradouro = ""
            if campo_logradouro:
                logradouro = str(row[idx] or "").strip()
                idx += 1
            oid = row[idx]
            geom = row[idx + 1]
            if not geom:
                continue
            logradouro = logradouro or f"Eixo {oid}"
            chave = slug_resultado(logradouro)
            usados[chave] = usados.get(chave, 0) + 1
            sufixo = f"_{usados[chave]}" if usados[chave] > 1 else ""
            try:
                geom_utm = geom.projectAs(sr_utm)
            except Exception:
                geom_utm = geom
            prefixo = f"E{len(dados) + 1:02d}"
            dados.append(
                {
                    "municipio": municipio,
                    "bairro": bairro,
                    "numero_processo": numero,
                    "logradouro": logradouro,
                    "identificador": f"{chave}{sufixo}",
                    "extensao": float(getattr(geom_utm, "length", 0) or 0),
                    "segmentos": _segmentos_linha(arcpy, geom, prefixo=prefixo),
                    "responsavel": responsavel or {},
                    "local_data": f"Sao Luis - MA, {dt.datetime.now().strftime('%d/%m/%Y')}.",
                }
            )
    return sorted(dados, key=lambda item: (slug_resultado(item["logradouro"]), item["identificador"]))


def _logo_existente():
    candidatos = [
        Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_Maranhão_(2023-2027).png"),
        Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_MaranhÃ£o_(2023-2027).png"),
        Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_MaranhÃƒÂ£o_(2023-2027).png"),
    ]
    for caminho in candidatos:
        if caminho.exists():
            return str(caminho)
    return None


def gerar_pdf_memorial(dados, saida_pdf):
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

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
    story.extend(
        [
            Paragraph("ESTADO DO MARANHAO", styles["cabecalho"]),
            Paragraph("SECRETARIA DE ESTADO DA AGRICULTURA FAMILIAR - SAF", styles["cabecalho"]),
            Paragraph("INSTITUTO DE COLONIZACAO E TERRAS DO MARANHAO - ITERMA", styles["cabecalho"]),
            Spacer(1, 0.6 * cm),
            Paragraph("MEMORIAL DESCRITIVO LINEAR DO EIXO VIARIO", styles["titulo"]),
            Spacer(1, 0.45 * cm),
            Paragraph(f"Municipio/UF: {html.escape(dados['municipio'])} - MA", styles["normal"]),
            Paragraph(f"Bairro/Nucleo: {html.escape(dados['bairro'])}", styles["normal"]),
            Paragraph(f"Processo: {html.escape(dados.get('numero_processo', ''))}", styles["normal"]),
            Paragraph(f"Logradouro/Eixo: {html.escape(str(dados['logradouro']))}", styles["normal"]),
            Spacer(1, 0.25 * cm),
            Paragraph(f"Extensao linear: {decimal_texto(dados['extensao'], 2)} m", styles["normal"]),
            Spacer(1, 0.65 * cm),
            Paragraph("_" * 100, styles["cabecalho"]),
            Paragraph("DESCRICAO LINEAR DO EIXO", styles["titulo"]),
            Paragraph("_" * 100, styles["cabecalho"]),
            Spacer(1, 0.25 * cm),
            Paragraph(html.escape(_descricao_segmentos(dados)), styles["justificado"]),
            Spacer(1, 0.35 * cm),
            Paragraph(
                "Todas as coordenadas aqui descritas estao georreferenciadas ao Sistema Geodesico Brasileiro (SGB) "
                "e encontram-se representadas no Sistema UTM, referenciadas ao SIRGAS 2000, Fuso 23S. "
                "Por se tratar de geometria linear, este memorial apresenta apenas extensao, vertices, azimutes "
                "e distancias do eixo viario, sem calculo de area.",
                styles["justificado"],
            ),
            Spacer(1, 0.65 * cm),
            Paragraph(html.escape(dados.get("local_data", "")), styles["cabecalho"]),
            Spacer(1, 1.0 * cm),
            Paragraph("________________________________________", styles["assinatura"]),
            Paragraph("Responsavel Tecnico", styles["assinatura"]),
            Paragraph(html.escape(dados.get("responsavel", {}).get("nome", "")), styles["assinatura"]),
            Paragraph(html.escape(dados.get("responsavel", {}).get("formacao", "")), styles["assinatura"]),
            Paragraph(html.escape(dados.get("responsavel", {}).get("registro", "")), styles["assinatura"]),
        ]
    )
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


def _python_externo():
    candidatos = [Path(r"C:\Users\gusta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")]
    for caminho in candidatos:
        if caminho.exists() and caminho.is_file():
            return str(caminho)
    return None


def _renderizar_pdf(dados_json, saida_pdf):
    dados = json.loads(Path(dados_json).read_text(encoding="utf-8"))
    try:
        return gerar_pdf_memorial(dados, saida_pdf)
    except Exception:
        python_externo = _python_externo()
        if not python_externo:
            raise
        env = os.environ.copy()
        for chave in ["PYTHONHOME", "PYTHONPATH", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "CONDA_PYTHON_EXE"]:
            env.pop(chave, None)
        env["PYTHONNOUSERSITE"] = "1"
        resultado = subprocess.run(
            [python_externo, str(Path(__file__)), "--render-json", str(dados_json), "--saida", str(saida_pdf)],
            cwd=str(PASTA_FERRAMENTA),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if not Path(saida_pdf).exists():
            raise RuntimeError(resultado.stderr or resultado.stdout or "Falha ao renderizar PDF.")
        return str(saida_pdf)


def _mesclar_pdfs(pdfs, saida_pdf):
    try:
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        for pdf in pdfs:
            reader = PdfReader(str(pdf))
            for page in reader.pages:
                writer.add_page(page)
        with open(saida_pdf, "wb") as arquivo:
            writer.write(arquivo)
        return str(saida_pdf)
    except Exception:
        return None


def gerar_memoriais_eixos_por_json(input_json):
    preparar_imports()
    import arcpy
    from responsaveis_tecnicos import resolver_responsavel

    dados = input_json.get("dados", {}) or {}
    municipio = dados.get("municipio") or input_json.get("municipio") or "Peri Mirim"
    bairro = dados.get("bairro") or input_json.get("bairro") or ""
    numero = dados.get("numeroProcessoColetivo") or input_json.get("numeroProcessoColetivo") or ""
    shp_eixo = input_json.get("eixoViario") or input_json.get("shpEixoViario") or dados.get("eixoViario")
    if not shp_eixo or not arcpy.Exists(shp_eixo):
        raise ValueError("Informe eixoViario apontando para a camada de linhas do eixo viario.")

    pasta_saida = Path(
        input_json.get("pastaSaidaMemoriaisEixos")
        or PASTA_FERRAMENTA
        / "resultados"
        / "memoriais_eixos"
        / slug_resultado(municipio)
        / slug_resultado(bairro)
        / slug_resultado(numero)
    )
    pasta_json = pasta_saida / "dados_json"
    pasta_pdf = pasta_saida / "pdfs"
    pasta_json.mkdir(parents=True, exist_ok=True)
    pasta_pdf.mkdir(parents=True, exist_ok=True)

    responsavel = resolver_responsavel(input_json)
    memoriais = _dados_eixos(arcpy, shp_eixo, municipio, bairro, numero, responsavel)
    pdfs = []
    jsons = []
    for item in memoriais:
        nome_base = f"MEMORIAL_EIXO_{slug_resultado(item['identificador']).upper()}_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}"
        json_path = pasta_json / f"{nome_base}.json"
        pdf_path = pasta_pdf / f"{nome_base}.pdf"
        json_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        _renderizar_pdf(json_path, pdf_path)
        jsons.append(str(json_path))
        pdfs.append(str(pdf_path))

    consolidado = pasta_saida / f"MEMORIAIS_EIXOS_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}_COMPLETO.pdf"
    consolidado_final = _mesclar_pdfs(pdfs, consolidado)
    return {
        "pronto": True,
        "municipio": municipio,
        "bairro": bairro,
        "numeroProcessoColetivo": numero,
        "pastaSaida": str(pasta_saida),
        "pastaPDFs": str(pasta_pdf),
        "quantidadeEixos": len(pdfs),
        "pdfs": pdfs,
        "jsons": jsons,
        "pdfConsolidado": consolidado_final,
    }


def main():
    parser = argparse.ArgumentParser(description="Gera memoriais lineares dos eixos viarios.")
    parser.add_argument("--input")
    parser.add_argument("--saida-json")
    parser.add_argument("--render-json")
    parser.add_argument("--saida")
    args = parser.parse_args()

    if args.render_json:
        print(gerar_pdf_memorial(json.loads(Path(args.render_json).read_text(encoding="utf-8")), args.saida))
        return
    if not args.input:
        raise ValueError("Informe --input.")
    saida = gerar_memoriais_eixos_por_json(json.loads(Path(args.input).read_text(encoding="utf-8")))
    if args.saida_json:
        Path(args.saida_json).write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
